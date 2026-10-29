"""
Report totals for payment requests.

The functions take a queryset instead of a user, so they only add things up:
who may see which requests is decided once, by the caller, using the same
rule as the request list (visible_requests). A report can therefore never
show a request the user couldn't open.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Count, QuerySet, Sum
from django.db.models.functions import TruncMonth

from apps.payment_requests.models import PaymentRequest
from apps.payments.models import PaymentTransaction

ZERO = Decimal('0.00')

# "Paid on 31 October" means 31 October in Kenya, where the money moves. The
# database stores UTC, so a payment at 01:00 on 1 November in Nairobi is
# 22:00 on 31 October in UTC and would land in the wrong month. Kenya has no
# daylight saving, so this zone is a constant +3 all year. The named zone (not
# a fixed-offset object) is what Django's database time functions accept when
# bucketing months, and tzdata is a project dependency, so it resolves on the
# SQLite dev database and Postgres alike.
REPORT_TZ = ZoneInfo('Africa/Nairobi')


def _money(value) -> str:
    """A 2dp string such as "24500.00", the same format the request API uses.

    Sum() gives None when there are no rows, which is shown as "0.00".
    Strings, not floats, so no amount is ever rounded on the way to the browser.
    """
    return str((value or ZERO).quantize(ZERO))


def filter_requests(
    qs: QuerySet[PaymentRequest],
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    paid_from: date | None = None,
    paid_to: date | None = None,
) -> QuerySet[PaymentRequest]:
    """Narrow the requests before they are added up. None means "don't filter".

    Takes the already-visible queryset, so a filter can only narrow what the
    user may see, never widen it. Both date ranges are inclusive at both ends,
    so date_to=2026-10-31 includes 31 October.

    date_from/date_to use the request's own date ("requests raised in
    October"). paid_from/paid_to use when the successful payment completed
    ("money paid out in October"), so they only ever match paid requests.
    """
    if status is not None:
        qs = qs.filter(status=status)
    if date_from is not None:
        qs = qs.filter(date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(date__lte=date_to)
    if paid_from is not None or paid_to is not None:
        qs = qs.filter(id__in=_paid_between(paid_from, paid_to))
    return qs


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=REPORT_TZ)


def _paid_between(paid_from: date | None, paid_to: date | None):
    """Ids of requests whose successful payment completed in the range (Kenyan days).

    A subquery (id__in) rather than a join, so the totals can never count a
    request twice, whatever transactions it has. Only SUCCESS counts: a failed
    attempt moved no money. paid_to is turned into "before midnight at the
    start of the next day", which includes the whole of the last day.
    """
    txns = PaymentTransaction.objects.filter(status=PaymentTransaction.SUCCESS)
    if paid_from is not None:
        txns = txns.filter(completed_at__gte=_start_of_day(paid_from))
    if paid_to is not None:
        txns = txns.filter(completed_at__lt=_start_of_day(paid_to + timedelta(days=1)))
    return txns.values('request_id')


def _totals(qs: QuerySet[PaymentRequest]) -> dict:
    agg = qs.aggregate(count=Count('id'), total=Sum('amount'))
    return {'count': agg['count'], 'total': _money(agg['total'])}


def totals_by_status(qs: QuerySet[PaymentRequest]) -> list[dict]:
    """Every status in lifecycle order, including ones with no requests,
    so a dashboard always has the same rows."""
    rows = {
        row['status']: row
        for row in qs.order_by().values('status').annotate(count=Count('id'), total=Sum('amount'))
    }
    return [
        {
            'status': status,
            'label': label,
            'count': rows.get(status, {}).get('count', 0),
            'total': _money(rows.get(status, {}).get('total')),
        }
        for status, label in PaymentRequest.STATUS_CHOICES
    ]


def _totals_by(qs: QuerySet[PaymentRequest], field: str) -> list[dict]:
    """Totals per project or vendor, biggest total first, then by name."""
    rows = (
        qs.order_by()
        .values(f'{field}_id', f'{field}__name')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total', f'{field}__name')
    )
    return [
        {
            'id': row[f'{field}_id'],
            'name': row[f'{field}__name'],
            'count': row['count'],
            'total': _money(row['total']),
        }
        for row in rows
    ]


def totals_by_project(qs: QuerySet[PaymentRequest]) -> list[dict]:
    return _totals_by(qs, 'project')


def totals_by_vendor(qs: QuerySet[PaymentRequest]) -> list[dict]:
    return _totals_by(qs, 'vendor')


def _shift_month(day: date, delta: int) -> date:
    """Move a first-of-month date by whole months, without dateutil."""
    index = day.year * 12 + (day.month - 1) + delta
    return date(index // 12, index % 12 + 1, 1)


def totals_by_month(
    qs: QuerySet[PaymentRequest],
    months: int = 6,
    today: date | None = None,
) -> list[dict]:
    """Requests raised and money paid per month, oldest first.

    Always returns exactly `months` buckets, including empty ones, so the
    dashboard's trend line has a stable shape. Requests are bucketed by their
    own date ("raised in October"); `paid` uses the successful payment's
    completed_at in Kenyan time ("money moved in October"). Both series only
    ever cover the requests in `qs`, so the caller's visibility rule still
    applies. One query per series, not one per month.
    """
    if months < 1:
        return []

    today = today or datetime.now(REPORT_TZ).date()
    first = _shift_month(today.replace(day=1), -(months - 1))

    buckets = []
    cursor = first
    for _ in range(months):
        key = f'{cursor.year:04d}-{cursor.month:02d}'
        buckets.append({'month': key, 'count': 0, 'total': _money(None), 'paid_count': 0, 'paid': _money(None)})
        cursor = _shift_month(cursor, 1)
    by_key = {bucket['month']: bucket for bucket in buckets}

    raised = (
        qs.annotate(month=TruncMonth('date'))
        .order_by()
        .values('month')
        .annotate(count=Count('id'), total=Sum('amount'))
    )
    for row in raised:
        if row['month'] is None:
            continue
        bucket = by_key.get(row['month'].strftime('%Y-%m'))
        if bucket is not None:
            bucket['count'] = row['count']
            bucket['total'] = _money(row['total'])

    paid = (
        PaymentTransaction.objects
        .filter(status=PaymentTransaction.SUCCESS, request__in=qs)
        .annotate(month=TruncMonth('completed_at', tzinfo=REPORT_TZ))
        .order_by()
        .values('month')
        .annotate(count=Count('id'), total=Sum('amount'))
    )
    for row in paid:
        if row['month'] is None:
            continue
        bucket = by_key.get(row['month'].strftime('%Y-%m'))
        if bucket is not None:
            bucket['paid_count'] = row['count']
            bucket['paid'] = _money(row['total'])

    return buckets


def summary(qs: QuerySet[PaymentRequest]) -> dict:
    """The whole report: overall, the two figures a dashboard headlines, and the breakdowns."""
    return {
        'overall': _totals(qs),
        'pending_approval': _totals(qs.filter(status=PaymentRequest.PENDING_APPROVAL)),
        'paid': _totals(qs.filter(status=PaymentRequest.PAID)),
        'by_status': totals_by_status(qs),
        'by_project': totals_by_project(qs),
        'by_vendor': totals_by_vendor(qs),
        'by_month': totals_by_month(qs),
    }
