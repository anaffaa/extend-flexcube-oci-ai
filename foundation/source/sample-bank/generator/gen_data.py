"""Synthetic data generator for the FLEXCUBE UBS 14.4 demo subset (Oasis Demo Bank, UAE).

Deterministic: the same SEED always produces identical files.
Usage: python3 gen_data.py [--customers 2000] [--out ../data]
"""
import argparse, calendar, collections, datetime as dt, heapq, math, os, random, string, zlib
from refdata import *
from writer import TableWriter, MANIFEST

SEED = 20261021
WIN_START = dt.date(2025, 10, 1)        # first day of transaction history
HIST_END = dt.date(2026, 10, 20)        # last end of day processed (ACTB_HISTORY)
TODAY = dt.date(2026, 10, 21)           # current branch date (ACTB_DAILY_LOG)
CUTOFF = dt.datetime(2026, 10, 21, 11, 30)
STRUCT_THRESHOLD = 55000                # demo cash reporting threshold, configurable

R = random.Random(SEED)


# ----------------------------------------------------------------------------- helpers
def money(x, dec=2):
    return round(x + 1e-9, dec)


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def rdate(a, b):
    return a + dt.timedelta(days=R.randint(0, max(0, (b - a).days)))


def at(d, h0=8, h1=22):
    return dt.datetime(d.year, d.month, d.day, R.randint(h0, h1 - 1), R.randint(0, 59), R.randint(0, 59))


def months_in_window():
    d = WIN_START
    while d <= TODAY:
        yield d
        d = add_months(d, 1)


def wpick(d):
    keys, w = list(d), list(d.values())
    return R.choices(keys, w)[0]


def logu(a, b):
    return math.exp(R.uniform(math.log(a), math.log(b)))


def poisson(lam):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= R.random()
        if p <= L:
            return k
        k += 1


def stable(s):
    return zlib.crc32(str(s).encode())


def safe_sample(pool, k):
    return R.sample(pool, min(k, len(pool)))


def julian(d):
    return f'{d.year % 100:02d}{d.timetuple().tm_yday:03d}'


B36 = string.digits + string.ascii_uppercase


def b36(n, w):
    s = ''
    for _ in range(w):
        s = B36[n % 36] + s
        n //= 36
    return s


def iban(acno):
    bban = BANK_ID_IBAN + acno.rjust(16, '0')
    num = ''.join(str(int(c, 36)) for c in bban + 'AE00')
    return f'AE{98 - int(num) % 97:02d}{bban}'


def digits(n):
    return ''.join(R.choice(string.digits) for _ in range(n))


EMIRATE_BRANCHES = collections.defaultdict(list)
for b in BRANCHES:
    EMIRATE_BRANCHES[b[2]].append(b[0])
EMIRATE_BRANCHES['Dubai'] = ['001', '002', '003', '004']     # head office has no walk-in customers


# ----------------------------------------------------------------------------- entities
class Cust:
    __slots__ = ('no', 'type', 'name', 'first', 'middle', 'last', 'short', 'nat', 'sex', 'dob', 'emirate', 'area',
                 'branch', 'cat', 'cif_date', 'occ', 'salary', 'pay_day', 'employer', 'employer_name', 'income_src',
                 'pep', 'kyc_level', 'score', 'accounts', 'primary', 'loans', 'cards', 'scen', 'job_loss',
                 'rehire', 'churn', 'churn_close', 'sector', 'size', 'turnover', 'employees', 'cash_int',
                 'cross_border', 'od_limit', 'revenue_drop', 'payroll_internal', 'legal', 'incorp', 'license',
                 'trn', 'staff_ids', 'kyc_review', 'passport_exp', 'visa_exp', 'married', 'children', 'rent',
                 'remit', 'travel', 'email', 'mobile', 'eid', 'passport', 'rm', 'dormant')

    def __init__(self, **kw):
        for s in self.__slots__:
            setattr(self, s, kw.get(s))


class Acct:
    __slots__ = ('no', 'branch', 'cust', 'cls', 'ccy', 'open', 'bal', 'opening', 'dormant', 'dorm_since',
                 'reactivated', 'last_dr', 'last_cr', 'closed', 'iban', 'salary', 'td', 'od', 'kind',
                 'mtd_dr', 'mtd_cr', 'today_dr', 'today_cr', 'open_today', 'pending')

    def __init__(self, **kw):
        for s in self.__slots__:
            setattr(self, s, kw.get(s))
        self.pending = []


CUSTS, ACCTS, LOANS, LABELS = [], {}, [], []
CORPS = []
_ac_seq = collections.Counter()
_cust_seq = [0]
CLASS = {c[0]: c for c in ACCOUNT_CLASSES}
TYPECODE = {'SAVIND': '01', 'CURIND': '02', 'SALIND': '03', 'PRISAV': '04', 'CURSME': '05', 'CURCOR': '06',
            'USDCUR': '07', 'TDRETL': '08', 'TDCORP': '09'}


def new_cust_no(branch):
    _cust_seq[0] += 1
    return f'{branch}{_cust_seq[0]:06d}'


def new_account(cust, cls, open_d, ccy='AED', bal=0.0):
    _ac_seq[cls] += 1
    no = f'{cust.branch}{TYPECODE[cls]}{_ac_seq[cls] + 10000000:08d}'
    a = Acct(no=no, branch=cust.branch, cust=cust, cls=cls, ccy=ccy, open=open_d, bal=money(bal), opening=money(bal),
             dormant=False, closed=None, iban=iban(no), salary=(cls == 'SALIND'), td=None, od=0.0,
             kind=CLASS[cls][2], mtd_dr=0.0, mtd_cr=0.0, today_dr=0.0, today_cr=0.0)
    ACCTS[no] = a
    cust.accounts.append(a)
    return a


def person_name(nat, sex):
    grp, lastkey = NAME_GROUP[nat]
    first = R.choice(FIRST[f'{grp}_{sex}'])
    middle = R.choice(FIRST[f'{grp}_M']) if grp in ('GULF', 'PK', 'EG', 'LEV', 'BD') and R.random() < .7 else ''
    if middle == first:
        middle = ''
    last = R.choice(LAST[lastkey])
    return first, middle, last


# ----------------------------------------------------------------------------- corporates
def build_corporates(n):
    used = set()
    for _ in range(n):
        sector = R.choice(SECTORS)
        while True:
            name = f'{R.choice(CORP_PREFIX)} {sector[0]} {R.choice(LEGAL)}'
            if name not in used:
                used.add(name)
                break
        size = R.choices(['MICRO', 'SMALL', 'MEDIUM', 'LARGE'], [.42, .36, .16, .06])[0]
        turnover = {'MICRO': logu(6e5, 3e6), 'SMALL': logu(3e6, 2e7), 'MEDIUM': logu(2e7, 1.5e8),
                    'LARGE': logu(1.5e8, 9e8)}[size]
        emirate = wpick({'Dubai': .62, 'Abu Dhabi': .18, 'Sharjah': .12, 'Ajman': .04, 'Ras Al Khaimah': .04})
        branch = '004' if emirate == 'Dubai' and R.random() < .45 else R.choice(EMIRATE_BRANCHES[emirate])
        incorp = rdate(dt.date(1996, 1, 1), dt.date(2024, 6, 30))
        cif_date = max(incorp + dt.timedelta(days=R.randint(10, 400)), dt.date(2008, 1, 1))
        cif_date = min(cif_date, dt.date(2025, 9, 1))
        c = Cust(no=new_cust_no(branch), type='C', name=name, short=name[:20].upper(), nat='AE', emirate=emirate,
                 area=R.choice(AREAS[emirate]), branch=branch, cat='SME' if turnover < 5e7 else 'CORPORATE',
                 cif_date=cif_date, sector=sector, size=size, turnover=turnover,
                 employees=max(2, int(turnover / logu(2.5e5, 7e5))), cash_int=sector[3], cross_border=sector[4],
                 legal=name.split()[-1], incorp=incorp, license=f'CN-{digits(7)}', trn='100' + digits(12),
                 accounts=[], loans=[], cards=[], scen=set(), staff_ids=[], pep=False, payroll_internal=0.0,
                 rm=f'RM{R.randint(1, 25):03d}', dormant=False)
        c.kyc_level = {'L': 'Level1', 'M': 'Level2', 'H': 'Level3'}[sector[2]]
        if c.kyc_level == 'Level3' and R.random() < .4:
            c.kyc_level = 'Level2'
        c.score = max(1, min(10, int(R.gauss(6, 1.7))))            # internal rating 1 (best) to 10
        c.kyc_review = add_months(cif_date, 12 * R.randint(1, 3))
        while c.kyc_review < dt.date(2025, 1, 1):
            c.kyc_review = add_months(c.kyc_review, 12 * (1 if c.kyc_level == 'Level3' else 3))
        if R.random() < .07:
            c.kyc_review = rdate(dt.date(2025, 6, 1), dt.date(2026, 9, 30))   # review overdue
        cls = 'CURSME' if c.cat == 'SME' else 'CURCOR'
        monthly = turnover / 12
        main = new_account(c, cls, cif_date, bal=monthly * R.uniform(.25, 1.8))
        c.primary = main
        c.od_limit = money(max(monthly * R.uniform(.1, .4) if R.random() < .55 else 0, c.employees * 7500 * 1.5), -3)
        main.od = c.od_limit
        if c.cross_border and R.random() < .45:
            new_account(c, 'USDCUR', add_months(cif_date, R.randint(0, 24)), 'USD',
                        bal=monthly * R.uniform(.05, .5) / CCY_RATE['USD'])
        if R.random() < .14:
            td = new_account(c, 'TDCORP', rdate(dt.date(2024, 1, 1), dt.date(2026, 9, 15)),
                             bal=money(min(monthly * R.uniform(.5, 3), 2.5e7), 0))
            setup_td(td)
        CUSTS.append(c)
        CORPS.append(c)


# ----------------------------------------------------------------------------- individuals
def build_individuals(n):
    employers = [c for c in CORPS]
    emp_weights = [c.employees for c in employers]
    for _ in range(n):
        nat = wpick(NATIONALITY_WEIGHTS)
        sex = 'M' if R.random() < .63 else 'F'
        first, middle, last = person_name(nat, sex)
        age = int(min(68, max(21, R.gauss(37, 9))))
        dob = rdate(dt.date(TODAY.year - age - 1, TODAY.month, 1), dt.date(TODAY.year - age, TODAY.month, 1))
        emirate = wpick(EMIRATE_WEIGHTS)
        branch = R.choice(EMIRATE_BRANCHES[emirate])
        if nat == 'AE':
            occ = R.choices([o for o in OCCUPATIONS], [.02, .01, .08, .05, .10, .10, .04, .50, .05, .04, .01])[0]
        else:
            occ = R.choices(OCCUPATIONS, [o[2] for o in OCCUPATIONS])[0]
        if age > 60 and R.random() < .6:
            occ = OCCUPATIONS[9]
        lo, hi = occ[1]
        salary = money(logu(lo, hi), 0) if hi else 0.0
        earliest = max(dt.date(2008, 1, 1), dt.date(dob.year + 21, dob.month, 1))
        cif_date = rdate(earliest, dt.date(2026, 6, 30)) if earliest < dt.date(2026, 6, 30) else dt.date(2026, 6, 30)
        c = Cust(no=new_cust_no(branch), type='I', first=first, middle=middle, last=last, nat=nat, sex=sex, dob=dob,
                 emirate=emirate, area=R.choice(AREAS[emirate]), branch=branch, cif_date=cif_date, occ=occ[0],
                 salary=salary, accounts=[], loans=[], cards=[], scen=set(), pep=R.random() < .012, dormant=False)
        c.name = ' '.join(x for x in (first, middle, last) if x)
        c.short = (first[:1] + ' ' + last)[:20].upper()
        c.score = int(min(900, max(300, R.gauss(700, 75))))      # bureau score at origination time
        c.married = R.random() < (.25 if age < 28 else .7)
        c.children = R.choice([0, 1, 2, 2, 3, 4]) if c.married else 0
        c.eid = f'784-{dob.year}-{digits(7)}-{R.randint(0, 9)}'
        c.passport = R.choice(string.ascii_uppercase) + R.choice(string.ascii_uppercase) + digits(7)
        c.passport_exp = rdate(dt.date(2025, 3, 1), dt.date(2034, 12, 31))
        c.visa_exp = None if nat == 'AE' else rdate(dt.date(2025, 6, 1), dt.date(2028, 12, 31))
        dom = 'example.com'
        c.email = f'{first.split()[0].lower()}.{last.replace(" ", "").lower()}{R.randint(1, 999)}@{dom}'
        c.mobile = f'9715{R.choice("024568")}{digits(7)}'
        c.remit = REMIT_PROPENSITY.get(nat, .03) * R.uniform(.5, 1.4) if nat != 'AE' else 0.0
        c.travel = R.random() < (.45 if salary > 20000 else .2)
        c.rent = (R.random() < .55) if nat != 'AE' else (R.random() < .15)
        c.pay_day = 22 if occ[0] == 'Government Employee' else R.choice([25, 26, 27, 28, 28, 1])
        # income source and employer
        if occ[0] in ('Self-Employed',):
            c.income_src = 'BUSINESS'
        elif occ[0] == 'Retired':
            c.income_src, c.employer_name = 'PENSION', 'General Pension Authority Demo'
        elif occ[0] == 'Homemaker or Student':
            c.income_src = 'FAMILY'
        elif occ[0] == 'Government Employee':
            c.income_src, c.employer_name = 'SALARY', R.choice(['Federal Authority Demo', 'Municipality Demo',
                                                                'Government Department Demo', 'Public Utility Demo'])
        else:
            c.income_src = 'SALARY'
            fit = [(e, w) for e, w in zip(employers, emp_weights) if e.turnover / 12 * .08 >= salary]
            if fit and R.random() < .42:
                emp = R.choices([e for e, _ in fit], [w for _, w in fit])[0]
                c.employer, c.employer_name = emp, emp.name
                c.pay_day = (stable(emp.no) % 4) + 25
                emp.staff_ids.append(c)
            else:
                c.employer_name = f'{R.choice(CORP_PREFIX)} {R.choice(SECTORS)[0]} {R.choice(LEGAL)}'
        # category
        if salary >= 50000 or R.random() < .03:
            c.cat = 'PRIORITY'
            c.rm = f'RM{R.randint(1, 25):03d}'
        else:
            c.cat = 'INDIVIDUAL'
        if c.income_src == 'SALARY' and c.employer is None and R.random() < .02:
            c.cat, c.employer_name, c.pay_day = 'STAFF', BANK_NAME, 26
        # KYC risk
        lvl = 1
        if c.income_src == 'BUSINESS' or nat in ELEVATED_RISK_JURISDICTIONS:
            lvl = 2
        if c.pep:
            lvl = 3
        c.kyc_level = f'Level{lvl}'
        period = {1: 5, 2: 3, 3: 1}[lvl]
        c.kyc_review = add_months(cif_date, 12 * period)
        while c.kyc_review < dt.date(2025, 1, 1):
            c.kyc_review = add_months(c.kyc_review, 12 * period)
        if R.random() < .06:
            c.kyc_review = rdate(dt.date(2025, 3, 1), dt.date(2026, 9, 30))
        # accounts
        prim_cls = {'SALARY': 'SALIND', 'PENSION': 'SALIND', 'BUSINESS': 'CURIND', 'FAMILY': 'SAVIND'}[c.income_src]
        base = max(salary, 3000)
        prim = new_account(c, prim_cls, cif_date, bal=base * min(6, R.lognormvariate(-.2, .8)))
        c.primary = prim
        if c.cat == 'PRIORITY':
            new_account(c, 'PRISAV', rdate(cif_date, dt.date(2026, 8, 31)), bal=logu(1e5, 3e6))
        if R.random() < .42 and prim_cls != 'SAVIND':
            new_account(c, 'SAVIND', rdate(cif_date, dt.date(2026, 8, 31)), bal=base * R.uniform(.3, 10))
        if R.random() < .07:
            new_account(c, 'USDCUR', rdate(cif_date, dt.date(2026, 8, 31)), 'USD', bal=logu(500, 6e4))
        if R.random() < .12 and salary >= 8000:
            td = new_account(c, 'TDRETL', rdate(max(cif_date, dt.date(2024, 1, 1)), dt.date(2026, 9, 15)),
                             bal=money(min(logu(1e4, 15 * base), 5e6), 0))
            setup_td(td)
        # debit card on the primary account
        if R.random() < .93:
            c.cards.append(make_card(c, prim))
        CUSTS.append(c)


def finalize_corporates():
    for c in CORPS:
        internal = sum(e.salary for e in c.staff_ids)
        c.employees = max(c.employees, len(c.staff_ids))
        need = 1.5 * max(internal, c.employees * 7500)
        c.od_limit = c.primary.od = money(max(c.od_limit, need), -3)


def setup_td(td):
    tenor = R.choice([3, 6, 6, 12, 12, 24])
    rate = {3: 3.25, 6: 3.75, 12: 4.10, 24: 4.25}[tenor] + R.uniform(-.25, .25)
    td.td = {'tenor': tenor, 'rate': round(rate, 2), 'book': td.open, 'mat': add_months(td.open, tenor),
             'amount': td.bal, 'rollover': R.random() < .6}
    if td.open >= WIN_START:          # booked during the window: funded by a transfer event
        td.opening = td.bal = 0.0


_card_seq = [0]


def make_card(c, acct):
    _card_seq[0] += 1
    issued = max(acct.open + dt.timedelta(days=R.randint(3, 20)), rdate(dt.date(2022, 1, 1), dt.date(2025, 6, 30)))
    exp = add_months(issued, 60)
    return {'ref': f'DCR{_card_seq[0]:09d}', 'pan': f'400000******{R.randint(0, 9999):04d}', 'seq': '001',
            'cust': c, 'acct': acct, 'issued': issued, 'exp': exp,
            'product': 'PLAT' if c.cat == 'PRIORITY' else 'CLSC', 'status': 'A'}


# ----------------------------------------------------------------------------- loans
def annuity(p, rate, n):
    r = rate / 1200
    return p / n if r == 0 else p * r / (1 - (1 + r) ** -n)


_loan_seq = collections.Counter()


def book_loan(c, prod, amount, tenor, rate, book, repay_acct):
    p = LOAN[prod]
    _loan_seq[(c.branch, prod, book)] += 1
    no = f'{c.branch}{prod}{julian(book)}{_loan_seq[(c.branch, prod, book)]:04d}'
    emi = money(annuity(amount, rate, tenor))
    sched, bal, due = [], amount, add_months(book, 1)
    prev = book
    for k in range(1, tenor + 1):
        interest = money(bal * rate / 1200)
        principal = money(bal if k == tenor else emi - interest)
        bal = money(bal - principal)
        sched.append({'no': k, 'start': prev, 'due': due, 'prin': principal, 'int': interest,
                      'paid': None, 'paid_amt': 0.0, 'evt': None})
        prev, due = due, add_months(book, k + 1)
    L = {'no': no, 'cust': c, 'prod': prod, 'amount': money(amount), 'tenor': tenor, 'rate': round(rate, 2),
         'book': book, 'mat': sched[-1]['due'], 'emi': emi, 'sched': sched, 'acct': repay_acct, 'evt_seq': 1,
         'branch': c.branch, 'guarantor': None, 'down': 0.0}
    if prod in ('ALN1', 'HLN1'):
        L['down'] = money(amount * R.uniform(.2, .3) / .75, 0)
    LOANS.append(L)
    c.loans.append(L)
    return L


def build_loans():
    for c in CUSTS:
        if c.type == 'I':
            if c.income_src not in ('SALARY', 'PENSION') or c.salary < 5000 or R.random() > .30:
                continue
            dbr_room = .5 * c.salary
            prods = ['PLN1']
            if c.salary >= 25000 and R.random() < .3:
                prods = ['HLN1']
            elif R.random() < .32:
                prods = ['ALN1']
            if R.random() < .12:
                prods.append('ALN1' if prods[0] != 'ALN1' else 'PLN1')
            for prod in prods:
                lo_r, hi_r = LOAN[prod][4]
                lo_t, hi_t = LOAN[prod][5]
                rate = R.uniform(lo_r, hi_r) + (720 - c.score) / 300          # risk based pricing
                tenor = R.choice(range(lo_t, hi_t + 1, 12))
                if prod == 'PLN1':
                    amount = min(c.salary * R.uniform(4, 20), 20 * c.salary)
                elif prod == 'ALN1':
                    amount = min(logu(4e4, 3e5), c.salary * 14)
                else:
                    amount = min(logu(6e5, 4e6), c.salary * 75)
                emi = annuity(amount, rate, tenor)
                if emi > dbr_room:                         # central bank debt burden ratio cap of 50 percent
                    amount *= dbr_room / emi * R.uniform(.6, .98)
                    emi = annuity(amount, rate, tenor)
                if amount < 15000:
                    continue
                earliest = max(c.cif_date, add_months(WIN_START, -tenor + 2))
                book = rdate(earliest, dt.date(2026, 9, 30)) if earliest < dt.date(2026, 9, 30) else None
                if not book:
                    continue
                book_loan(c, prod, money(amount, 0), tenor, rate, book, c.primary)
                dbr_room -= emi
        elif c.cat == 'SME' and R.random() < .25:
            amount = min(c.turnover * R.uniform(.08, .35), 3e6)
            tenor = R.choice([24, 36, 48, 60])
            rate = R.uniform(*LOAN['SLN1'][4]) + (c.score - 5) * .25
            earliest = max(c.cif_date, add_months(WIN_START, -tenor + 2))
            book = rdate(earliest, dt.date(2026, 9, 30))
            book_loan(c, 'SLN1', money(amount, -3), tenor, rate, book, c.primary)
    # guarantors on a share of personal and SME loans
    indiv = [c for c in CUSTS if c.type == 'I']
    for L in LOANS:
        if L['prod'] in ('PLN1', 'SLN1') and R.random() < .09:
            g = R.choice(indiv)
            if g is not L['cust']:
                L['guarantor'] = g


# ----------------------------------------------------------------------------- scenarios
def label(c, acct, scen, start, end, note):
    LABELS.append({'CUSTOMER_NO': c.no, 'CUST_AC_NO': acct.no if acct else None, 'SCENARIO': scen,
                   'START_DATE': start, 'END_DATE': end, 'NOTES': note})
    c.scen.add(scen)


def assign_scenarios():
    indiv = [c for c in CUSTS if c.type == 'I']
    salaried = [c for c in indiv if c.income_src == 'SALARY']
    # dormant accounts and fully inactive customers
    for a in list(ACCTS.values()):
        if a.cls in ('SAVIND', 'USDCUR') and a.cust.type == 'I' and R.random() < .09 and a.open < dt.date(2023, 6, 1):
            make_dormant(a)
    for c in safe_sample([c for c in indiv if not c.loans], 45):
        c.dormant = True
        for a in c.accounts:
            if a.kind != 'T' and a.open < dt.date(2023, 6, 1):
                make_dormant(a)
    # job loss: risk driven by debt burden and bureau score, never by nationality or gender
    for c in salaried:
        if c.dormant:
            continue
        emi = sum(L['emi'] for L in c.loans if L['mat'] > WIN_START)
        dbr = emi / c.salary if c.salary else 0
        z = -4.2 + 3.2 * dbr + (680 - c.score) / 70 + (.6 if c.salary < 8000 else 0)
        p = 1 / (1 + math.exp(-z))
        if R.random() < p:
            c.job_loss = rdate(dt.date(2026, 1, 10), dt.date(2026, 8, 31))
            c.rehire = add_months(c.job_loss, R.randint(3, 6)) if R.random() < .3 else None
            label(c, c.primary, 'JOB_LOSS', c.job_loss, c.rehire, 'Salary credits stop; borrower may fall into arrears')
    # churn: salary moved to another bank, balances drained, some accounts closed
    pool = [c for c in salaried if not c.job_loss and not c.dormant and not c.scen]
    for c in safe_sample(pool, int(len(indiv) * .06)):
        c.churn = rdate(dt.date(2026, 2, 1), dt.date(2026, 9, 10))
        c.churn_close = add_months(c.churn, 1) + dt.timedelta(days=R.randint(0, 25)) \
            if (not c.loans and R.random() < .55) else None
        if c.churn_close and c.churn_close > HIST_END:
            c.churn_close = None
        label(c, c.primary, 'CHURN', c.churn, c.churn_close, 'Salary moved away, balance drained'
              + (', account closed' if c.churn_close else ''))
    free = lambda pool: [c for c in pool if not c.scen and not c.dormant and not c.loans]
    # AML: structuring of cash deposits below the reporting threshold
    cands = free([c for c in indiv if c.income_src in ('BUSINESS', 'SALARY') and c.salary < 20000])
    for c in safe_sample(cands, 5) + safe_sample(free([c for c in CORPS if c.cash_int and c.cat == 'SME']), 2):
        s = rdate(dt.date(2026, 2, 1), dt.date(2026, 6, 15))
        label(c, c.primary, 'AML_STRUCTURING', s, s + dt.timedelta(weeks=10),
              f'Repeated cash deposits just below AED {STRUCT_THRESHOLD:,} across branches, then SWIFT out')
    # AML: pass-through (rapid in and out of large international wires)
    for c in safe_sample(free([c for c in CORPS if c.sector[0] in ('General Trading', 'Electronics Trading',
                                                                    'Real Estate Brokers', 'Textiles')]), 4) + \
            safe_sample(free([c for c in indiv if c.salary and c.salary < 30000]), 2):
        s = rdate(dt.date(2025, 12, 1), dt.date(2026, 7, 1))
        label(c, c.primary, 'AML_PASS_THROUGH', s, s + dt.timedelta(weeks=14),
              'Large incoming wires forwarded abroad within 48 hours')
    # AML: money mule (low declared income, many third party credits, cash out)
    for c in safe_sample(free([c for c in indiv if 0 < c.salary < 6000]), 6):
        s = rdate(dt.date(2026, 3, 1), dt.date(2026, 8, 1))
        label(c, c.primary, 'AML_MONEY_MULE', s, s + dt.timedelta(weeks=8),
              'Many small credits from unrelated senders, fast ATM cash out; turnover far above declared income')
    # AML: dormant account reactivation
    dorm = [a for a in ACCTS.values() if a.dormant and not a.cust.scen and a.cust.type == 'I']
    for a in safe_sample(dorm, 5):
        s = rdate(dt.date(2026, 1, 15), dt.date(2026, 8, 15))
        a.reactivated = s
        label(a.cust, a, 'AML_DORMANT_REACTIVATION', s, s + dt.timedelta(days=21),
              'Dormant account reactivated, large inflow moved out within days')
    # card fraud: card not present burst abroad
    carded = [c for c in indiv if c.cards and not c.dormant and not c.scen]
    for c in safe_sample(carded, 10):
        s = rdate(dt.date(2025, 11, 1), dt.date(2026, 10, 15))
        label(c, c.primary, 'CARD_FRAUD_CNP', s, s, 'Burst of foreign e-commerce card transactions within minutes')
    # SME revenue drop (credit early warning)
    for c in [c for c in CORPS if c.loans]:
        if R.random() < .15:
            c.revenue_drop = rdate(dt.date(2025, 12, 1), dt.date(2026, 6, 30))
            label(c, c.primary, 'SME_REVENUE_DROP', c.revenue_drop, None, 'Receipts fall by about 70 percent')


def make_dormant(a):
    a.dormant = True
    a.dorm_since = rdate(dt.date(2022, 1, 1), dt.date(2024, 9, 30))
    a.last_dr = a.last_cr = a.dorm_since - dt.timedelta(days=365)
    a.bal = a.opening = money(min(a.bal, logu(50, 25000)))


# ----------------------------------------------------------------------------- event planning
EVENTS = []
_eseq = [0]


def ev(ts, kind, **kw):
    if ts.date() < WIN_START or ts > CUTOFF:
        return
    _eseq[0] += 1
    heapq.heappush(EVENTS, (ts, _eseq[0], kind, kw))


def active(a, d):
    if a.dormant and not (a.reactivated and d >= a.reactivated):
        return False
    return a.open <= d and not (a.closed and d >= a.closed)


def ext_party(country='AE'):
    return f'{R.choice(CORP_PREFIX)} {R.choice(SECTORS)[0]} {R.choice(LEGAL)}' if R.random() < .6 \
        else ' '.join(x for x in person_name(R.choice(list(NAME_GROUP)), R.choice('MF')) if x)


def plan_individual(c):
    if c.dormant:
        return
    p = c.primary
    sav = next((a for a in c.accounts if a.cls in ('SAVIND', 'PRISAV') and not a.dormant), None)
    for m0 in months_in_window():
        y, mo = m0.year, m0.month
        last = calendar.monthrange(y, mo)[1]
        churned = c.churn and m0 >= dt.date(c.churn.year, c.churn.month, 1)
        jobless = c.job_loss and m0 >= dt.date(c.job_loss.year, c.job_loss.month, 1) and \
            not (c.rehire and m0 >= dt.date(c.rehire.year, c.rehire.month, 1))
        # income
        payd = dt.date(y, mo, min(c.pay_day, last))
        if c.income_src in ('SALARY', 'PENSION') and not jobless and not churned:
            amt = c.salary * (R.uniform(.98, 1.02) if R.random() < .2 else 1.0)
            if c.rehire and m0 >= dt.date(c.rehire.year, c.rehire.month, 1):
                amt *= .8
            if mo == 12 and R.random() < .25:
                amt += c.salary * R.uniform(.5, 1.5)          # annual bonus
            ev(dt.datetime(y, mo, payd.day, 7, R.randint(0, 59)), 'SALARY', cust=c, acct=p, amount=money(amt, 0))
        elif c.income_src == 'BUSINESS' and not churned:
            target = c.salary * R.uniform(.6, 1.4)
            for _ in range(R.randint(2, 6)):
                d = dt.date(y, mo, R.randint(1, last))
                share = target * R.uniform(.1, .4)
                if R.random() < .5:
                    ev(at(d, 9, 20), 'EXT_IN', acct=p, amount=money(share, 0), trn='FTI', party=ext_party(),
                       details='INVOICE ' + digits(5))
                else:
                    ev(at(d, 9, 20), 'CASH_IN', acct=p, amount=money(share, -2), trn=R.choice(['CSD', 'CDM']),
                       branch=p.branch)
        elif c.income_src == 'FAMILY':
            ev(at(dt.date(y, mo, R.randint(1, 10)), 9, 18), 'EXT_IN', acct=p, amount=money(logu(2000, 12000), -2),
               trn='FTI', party=' '.join(x for x in person_name(c.nat, 'M') if x), details='FAMILY SUPPORT')
        if churned:
            if R.random() < .8:
                continue                                       # little activity after churn
        spend_base = c.salary if c.salary else 4000
        if jobless:
            spend_base *= .45
        # card spending
        n_pos = poisson(3 + 5 * min(spend_base / 20000, 2.2))
        budget = spend_base * R.uniform(.15, .32)
        weights = [R.lognormvariate(0, .9) for _ in range(n_pos)]
        tw = sum(weights) or 1
        for w in weights:
            d = dt.date(y, mo, R.randint(1, last))
            ev(at(d, 8, 23), 'CARD', cust=c, acct=p, amount=money(max(8, budget * w / tw)), trn='POS')
        for _ in range(poisson(1.2 + min(spend_base / 25000, 2))):
            ev(at(dt.date(y, mo, R.randint(1, last)), 0, 24), 'CARD', cust=c, acct=p,
               amount=money(logu(30, 900)), trn='ECM')
        n_atm = 1 + poisson(1.5 + (1.5 if jobless else 0))
        for _ in range(n_atm):
            amt = max(100, round(spend_base * R.uniform(.03, .1) / 100) * 100)
            ev(at(dt.date(y, mo, R.randint(1, last)), 7, 23), 'CARD', cust=c, acct=p, amount=float(min(amt, 5000)),
               trn='ATM')
        # bills
        for _ in range(R.randint(1, 3)):
            ev(at(dt.date(y, mo, R.randint(3, min(last, 20))), 9, 22), 'EXT_OUT', acct=p,
               amount=money(logu(120, 400 + spend_base * .03)), trn='BIL',
               party=R.choice(['Utility Authority Demo', 'Telecom Provider Demo', 'Internet Services Demo',
                               'District Cooling Demo']), details='BILL PAYMENT')
        # remittance home
        if c.remit and c.salary and not jobless and R.random() < .85:
            d = payd + dt.timedelta(days=R.randint(0, 5))
            if d.month == mo:
                ev(at(d, 9, 21), 'SWIFT_OUT', acct=p, amount=money(c.salary * c.remit * R.uniform(.7, 1.3), 0),
                   country=c.nat, party=' '.join(x for x in person_name(c.nat, R.choice('MF')) if x),
                   details='FAMILY SUPPORT')
        # rent by cheque, quarterly
        if c.rent and c.salary and mo % 3 == (stable(c.no) % 3):
            ev(at(dt.date(y, mo, R.randint(1, 10)), 10, 15), 'CHEQUE_OUT', acct=p,
               amount=money(c.salary * R.uniform(.6, 1.0), -2), party=f'{R.choice(CORP_PREFIX)} Properties LLC',
               details='RENT')
        # transfer to savings
        if sav and c.salary and not jobless and R.random() < .7:
            d = payd + dt.timedelta(days=R.randint(1, 3))
            if d.month == mo:
                ev(at(d, 8, 22), 'BOOK', src=p, dst=sav, amount=money(c.salary * R.uniform(.05, .18), -1),
                   details='SAVINGS')
        # travel abroad once or twice a year
        if c.travel and R.random() < .14:
            city = R.choice(FOREIGN_CITIES)
            start = dt.date(y, mo, R.randint(1, max(1, last - 8)))
            for _ in range(R.randint(3, 10)):
                ev(at(start + dt.timedelta(days=R.randint(0, 7)), 8, 23), 'CARD', cust=c, acct=p,
                   amount=money(logu(40, 1500)), trn='POS', foreign=city)
        # month end interest and charges
        for a in c.accounts:
            if a.kind in ('S', 'C') and not a.dormant:
                ev(dt.datetime(y, mo, last, 23, 30), 'MONTHEND', acct=a)
    # churn drain transfers
    if c.churn:
        for k in range(R.randint(2, 4)):
            ev(at(c.churn + dt.timedelta(days=7 + 9 * k), 9, 20), 'DRAIN', acct=p, share=R.uniform(.5, .9))
        if c.churn_close:
            ev(dt.datetime(c.churn_close.year, c.churn_close.month, c.churn_close.day, 12, 0), 'CLOSE', cust=c)


def plan_corporate(c):
    p = c.primary
    usd = next((a for a in c.accounts if a.cls == 'USDCUR'), None)
    monthly = c.turnover / 12
    n_r = {'MICRO': 6, 'SMALL': 12, 'MEDIUM': 22, 'LARGE': 35}[c.size]
    for m0 in months_in_window():
        y, mo = m0.year, m0.month
        last = calendar.monthrange(y, mo)[1]
        season = 1 + .15 * math.sin((mo - 3) / 12 * 2 * math.pi)
        rec = monthly * season * R.uniform(.85, 1.15)
        if c.revenue_drop and m0 >= c.revenue_drop.replace(day=1):
            rec *= .3
        k = max(2, poisson(n_r))
        ws = [R.lognormvariate(0, .8) for _ in range(k)]
        tw = sum(ws)
        for w in ws:
            amt = rec * w / tw
            d = dt.date(y, mo, R.randint(1, last))
            ch = R.random()
            if c.cash_int and ch < .2:
                ev(at(d, 9, 17), 'CASH_IN', acct=p, amount=money(amt, -2), trn='CSD', branch=p.branch)
            elif c.cross_border and ch < .35:
                cty = R.choice(['IN', 'CN', 'SA', 'OM', 'GB', 'TR', 'EG', 'SG', 'HK'])
                tgt = usd if usd else p
                ev(at(d, 9, 17), 'SWIFT_IN', acct=tgt, amount=money(amt if tgt.ccy == 'AED' else amt / CCY_RATE['USD']),
                   country=cty, party=ext_party(cty), details='INVOICE ' + digits(6))
            elif ch < .5:
                ev(at(d, 9, 17), 'CHEQUE_IN', acct=p, amount=money(amt), party=ext_party(), details='PAYMENT')
            else:
                ev(at(d, 8, 18), 'EXT_IN', acct=p, amount=money(amt), trn='FTI', party=ext_party(),
                   details='INV ' + digits(6))
        # payroll: internal employees by book transfer, the rest via WPS to other banks
        payroll_total = c.employees * R.uniform(4500, 7500)
        internal = sum(e.salary for e in c.staff_ids)
        payday = dt.date(y, mo, min(25 + stable(c.no) % 4, last))
        if payroll_total > internal:
            ev(dt.datetime(y, mo, payday.day, 6, 30), 'EXT_OUT', acct=p, amount=money(payroll_total - internal, 0),
               trn='FTO', party='WPS SALARY TRANSFER', details=f'WPS PAYROLL {calendar.month_abbr[mo].upper()} {y}',
               force=True)
        # suppliers
        pay = rec * R.uniform(.55, .75)
        k = max(1, poisson(n_r * .7))
        ws = [R.lognormvariate(0, .9) for _ in range(k)]
        tw = sum(ws)
        for w in ws:
            amt = pay * w / tw
            d = dt.date(y, mo, R.randint(1, last))
            if c.cross_border and R.random() < .3:
                src = usd if usd and R.random() < .6 else p
                ev(at(d, 9, 16), 'SWIFT_OUT', acct=src,
                   amount=money(amt if src.ccy == 'AED' else amt / CCY_RATE['USD']),
                   country=R.choice(['CN', 'IN', 'TR', 'DE', 'US', 'SG', 'HK', 'SA']), party=ext_party(),
                   details='SUPPLIER INV ' + digits(6))
            elif R.random() < .15:
                ev(at(d, 9, 16), 'CHEQUE_OUT', acct=p, amount=money(amt), party=ext_party(), details='SUPPLIER')
            else:
                ev(at(d, 8, 18), 'EXT_OUT', acct=p, amount=money(amt), trn='FTO', party=ext_party(),
                   details='SUPPLIER PAYMENT')
        ev(dt.datetime(y, mo, last, 23, 30), 'MONTHEND', acct=p)


def plan_scenarios():
    by = collections.defaultdict(list)
    for l in LABELS:
        by[l['SCENARIO']].append(l)
    custs = {c.no: c for c in CUSTS}
    for l in by['AML_STRUCTURING']:
        c, s = custs[l['CUSTOMER_NO']], l['START_DATE']
        acc = 0.0
        for wk in range(10):
            for _ in range(R.randint(2, 4)):
                d = s + dt.timedelta(days=7 * wk + R.randint(0, 6))
                amt = money(R.uniform(STRUCT_THRESHOLD * .78, STRUCT_THRESHOLD - 150), -2)
                acc += amt
                ev(at(d, 9, 20), 'CASH_IN', acct=c.primary, amount=amt, trn=R.choice(['CSD', 'CDM', 'CSD']),
                   branch=R.choice([b[0] for b in BRANCHES[1:]]), scen=True)
            if wk % 2 == 1:
                ev(at(s + dt.timedelta(days=7 * wk + 6), 10, 16), 'SWIFT_OUT', acct=c.primary,
                   amount=money(acc * R.uniform(.75, .9), 0), country=R.choice(['TR', 'HK', 'CN', 'SY']),
                   party=ext_party(), details='TRADE PAYMENT', scen=True)
                acc = 0.0
    for l in by['AML_PASS_THROUGH']:
        c, s = custs[l['CUSTOMER_NO']], l['START_DATE']
        for k in range(R.randint(4, 8)):
            d = s + dt.timedelta(days=12 * k + R.randint(0, 5))
            amt = money(logu(2e5, 2.2e6) * (.3 if c.type == 'I' else 1), 0)
            t = at(d, 9, 13)
            ev(t, 'SWIFT_IN', acct=c.primary, amount=amt, country=R.choice(['RU', 'HK', 'TR', 'CN', 'NG']),
               party=ext_party(), details='CONSULTANCY FEES', scen=True)
            ev(t + dt.timedelta(hours=R.randint(3, 44)), 'SWIFT_OUT', acct=c.primary,
               amount=money(amt * R.uniform(.92, .99), 0), country=R.choice(['IR', 'SY', 'HK', 'TR', 'MM', 'LB']),
               party=ext_party(), details='GOODS PURCHASE', scen=True)
    for l in by['AML_MONEY_MULE']:
        c, s = custs[l['CUSTOMER_NO']], l['START_DATE']
        for _ in range(R.randint(18, 40)):
            d = s + dt.timedelta(days=R.randint(0, 55))
            t = at(d, 8, 22)
            amt = money(logu(1500, 9500), 0)
            ev(t, 'EXT_IN', acct=c.primary, amount=amt, trn='FTI',
               party=' '.join(x for x in person_name(R.choice(list(NAME_GROUP)), R.choice('MF')) if x),
               details=R.choice(['GIFT', 'LOAN REPAY', 'ONLINE SALE', 'PAYMENT']), scen=True)
            for _ in range(R.randint(1, 2)):
                ev(t + dt.timedelta(minutes=R.randint(20, 300)), 'CARD', cust=c, acct=c.primary,
                   amount=float(min(5000, round(amt * R.uniform(.4, .6) / 100) * 100)), trn='ATM', scen=True,
                   atm_branch=R.choice([b[0] for b in BRANCHES]))
    for l in by['AML_DORMANT_REACTIVATION']:
        a = ACCTS[l['CUST_AC_NO']]
        s = l['START_DATE']
        amt = money(logu(5e4, 4e5), 0)
        ev(at(s, 9, 12), 'SWIFT_IN', acct=a, amount=amt if a.ccy == 'AED' else money(amt / CCY_RATE['USD']),
           country=R.choice(['HK', 'NG', 'RU', 'TR']), party=ext_party(), details='INVESTMENT RETURN', scen=True)
        for k in range(R.randint(3, 6)):
            ev(at(s + dt.timedelta(days=k + 1), 9, 20), 'CASH_OUT', acct=a, scen=True,
               amount=money((amt if a.ccy == 'AED' else amt / CCY_RATE['USD']) * R.uniform(.12, .22), -2))
    for l in by['CARD_FRAUD_CNP']:
        c, d = custs[l['CUSTOMER_NO']], l['START_DATE']
        t = dt.datetime(d.year, d.month, d.day, R.randint(0, 4), R.randint(0, 59))
        cty, city = R.choice(CNP_FRAUD_ORIGINS)
        for k in range(R.randint(6, 12)):
            ev(t + dt.timedelta(minutes=k * R.randint(1, 4)), 'CARD', cust=c, acct=c.primary,
               amount=money(logu(250, 3200)), trn='ECM', foreign=(cty, city, 'USD'), scen=True)


def plan_loans():
    for L in LOANS:
        if L['book'] >= WIN_START:
            ev(dt.datetime(L['book'].year, L['book'].month, L['book'].day, 10, 0), 'DSBR', loan=L)
        for s in L['sched']:
            if WIN_START <= s['due'] <= TODAY:
                ev(dt.datetime(s['due'].year, s['due'].month, s['due'].day, 3, 0), 'EMI', loan=L, inst=s)
            elif s['due'] < WIN_START:
                late = R.random() < .04
                s['paid'] = s['due'] + dt.timedelta(days=R.randint(1, 12) if late else 0)
                if s['paid'] >= WIN_START:
                    s['paid'] = s['due']
                s['paid_amt'] = money(s['prin'] + s['int'])
                L['evt_seq'] += 1
                s['evt'] = L['evt_seq']


def plan_tds():
    for a in ACCTS.values():
        if not a.td:
            continue
        t = a.td
        if t['mat'] < WIN_START and not t['rollover']:
            t['rollover'] = True
        if t['book'] >= WIN_START:
            src = a.cust.primary
            ev(dt.datetime(t['book'].year, t['book'].month, t['book'].day, 11, 0), 'TD_BOOK', acct=a, src=src)
        mat = t['mat']
        while mat <= TODAY:
            if mat >= WIN_START:
                ev(dt.datetime(mat.year, mat.month, mat.day, 4, 0), 'TD_MATURE', acct=a)
            if not t['rollover']:
                break
            mat = add_months(mat, t['tenor'])


# ----------------------------------------------------------------------------- posting engine
class Engine:
    def __init__(self, out):
        self.out = out
        hist_cols = ['TRN_REF_NO', 'EVENT_SR_NO', 'EVENT', 'AC_BRANCH', 'AC_NO', 'AC_CCY', 'DRCR_IND', 'TRN_CODE',
                     'AMOUNT_TAG', 'FCY_AMOUNT', 'EXCH_RATE', 'LCY_AMOUNT', 'RELATED_CUSTOMER', 'RELATED_ACCOUNT',
                     'RELATED_REFERENCE', 'MIS_FLAG', 'TRN_DT', 'VALUE_DT', 'TXN_INIT_DATE', 'FINANCIAL_CYCLE',
                     'PERIOD_CODE', 'INSTRUMENT_CODE', 'BANK_CODE', 'TYPE', 'CATEGORY', 'CUST_GL', 'MODULE',
                     'AC_ENTRY_SR_NO', 'IB', 'USER_ID', 'CURR_NO', 'BATCH_NO', 'PRINT_STAT', 'AUTH_ID', 'PRODUCT',
                     'EXTERNAL_REF_NO', 'DONT_SHOWIN_STMT', 'IC_BAL_INCLUSION', 'AML_EXCEPTION', 'STMT_DT',
                     'ENTRY_SEQ_NO', 'SAVE_TIMESTAMP', 'AUTH_TIMESTAMP', 'SOURCE_CODE', 'ORG_SOURCE']
        self.hist = TableWriter(out, 'ACTB_HISTORY', hist_cols)
        self.daily = TableWriter(out, 'ACTB_DAILY_LOG', hist_cols + ['BALANCE_UPD', 'DELETE_STAT', 'ON_LINE', 'AUTH_STAT'])
        self.ft = TableWriter(out, 'FTTB_CONTRACT_MASTER', [
            'CONTRACT_REF_NO', 'EVENT_SEQ_NO', 'VERSION_NO', 'PRODUCT_CODE', 'USER_REF_NUMBER', 'DR_VALUE_DATE',
            'CR_ACCOUNT_BRANCH', 'CR_ACCOUNT', 'CR_CCY', 'CR_AMOUNT', 'CR_VALUE_DATE', 'EXCHANGE_RATE',
            'TRANSFER_TYPE', 'EVENT_CODE', 'DR_ACCOUNT_BRANCH', 'DR_ACCOUNT', 'DR_CCY', 'DR_AMOUNT', 'LCY_EQUIV',
            'CHARGE_WHOM', 'RATE_TYPE', 'MSG_STATUS', 'SOURCE_CODE', 'SETTLEMENT_STATUS', 'PAYMENT_DETAILS1',
            'PAYMENT_DETAILS2', 'BY_ORDER_OF1', 'BY_ORDER_OF2', 'ULT_BENEFICIARY1', 'ULT_BENEFICIARY2',
            'ULT_BENEFICIARY4', 'BY_ORDER_OF4', 'ACC_WITH_INSTN', 'DR_IBAN', 'CR_IBAN', 'STATUS', 'TIME_RECEIVED',
            'ACCOUNTING_DATE', 'INTERNAL_REMARKS'])
        self.sw = TableWriter(out, 'SWTB_SETTLEMENT_HIST', [
            'MSG_TYPE', 'PAN', 'BRANCH_CODE', 'ACC', 'TXN_CODE', 'PROC_CODE', 'TXN_AMT', 'TXN_CCY_CODE', 'SETL_AMT',
            'SETL_CCY_CODE', 'BILL_AMT', 'BILL_CCY_CODE', 'TXN_DATE', 'TXN_TIME', 'STAN', 'ACQ_ID', 'TERM_ID',
            'CARD_ACCPTOR_ID', 'MERCHANT_ID', 'MERCHANT_NAME', 'MERCHANT_CITY', 'MERCHANT_COUNTRY',
            'MERCHANT_CATEGORY_CODE', 'RRN', 'AUTH_CODE', 'RESP_CODE', 'DOMESTIC_FLAG', 'SETL_ACC', 'NETWORK_ID',
            'STATUS', 'CHANNEL', 'EXTERNAL_REF_NO', 'P_KEY'])
        self.seq = 1000000000
        self.refseq = collections.Counter()
        self.extseq = 0
        self.daymov = collections.defaultdict(lambda: [0.0, 0.0])    # (acct, date) -> [dr, cr]
        self.aml = collections.defaultdict(lambda: [0, 0.0, 0, 0.0])
        self.stats = collections.Counter()

    # -- references
    def ref(self, branch, product, d):
        k = (branch, product, d)
        self.refseq[k] += 1
        n = self.refseq[k]
        return f'{branch}{product}{julian(d)}{n:04d}' if n < 10000 else f'{branch}{product}{julian(d)}{b36(n, 4)}'

    def ext(self, prefix):
        self.extseq += 1
        return f'{prefix}{self.extseq:013d}'[:16]

    # -- balance helpers
    def can_debit(self, a, amt, force=False):
        return force or a.bal - amt >= -a.od - 1e-6

    def move(self, a, drcr, amt, ts):
        d = ts.date()
        if drcr == 'D':
            a.bal = money(a.bal - amt, 3)
            a.last_dr = d
            self.daymov[(a.no, d)][0] += amt
        else:
            a.bal = money(a.bal + amt, 3)
            a.last_cr = d
            self.daymov[(a.no, d)][1] += amt
        if d == TODAY:
            if drcr == 'D':
                a.today_dr += amt
            else:
                a.today_cr += amt
        if d.year == TODAY.year and d.month == TODAY.month:
            if drcr == 'D':
                a.mtd_dr += amt
            else:
                a.mtd_cr += amt

    # -- accounting
    def post(self, ts, trn, legs, branch, product=None, event='INIT', evt_no=1, module=None, ext_ref=None,
             instrument=None, user=None, source='FLEXCUBE', ref=None, rel_ref=None):
        """legs: list of (acct_or_gl, 'D'/'C', amount_in_account_ccy, amount_tag)."""
        t = TRN[trn]
        module = module or t[2]
        product = product or t[3]
        d = ts.date()
        ref = ref or self.ref(branch, product, d)
        writer = self.daily if d == TODAY else self.hist
        cust = None
        for x, _, _, _ in legs:
            if isinstance(x, Acct):
                cust = x.cust.no
                cust_acct = x.no
                break
        user = user or {'SW': 'SWITCH', 'IC': 'SYSTEM', 'CL': 'SYSTEM', 'RT': f'TLR{branch}A', 'CG': f'CLG{branch}',
                        'FT': 'NETBANK', 'PC': 'NETBANK'}.get(module, 'SYSTEM')
        auth = 'SYSTEM' if user in ('SWITCH', 'SYSTEM', 'NETBANK') else f'CHK{branch}'
        save_ts = ts
        for i, (x, drcr, amt, tag) in enumerate(legs, 1):
            self.seq += 1
            if isinstance(x, Acct):
                rate = CCY_RATE[x.ccy]
                lcy = money(amt * rate)
                row = [ref, evt_no, event, x.branch, x.no, x.ccy, drcr, trn, tag,
                       money(amt) if x.ccy != LCY else None, rate if x.ccy != LCY else None, lcy, x.cust.no, None,
                       rel_ref, 'N', d, d, d, f'FY{d.year}', f'M{d.month:02d}', instrument, BANK_CODE, None, '2', 'A',
                       module, self.seq, 'Y' if x.branch != branch else 'N', user, 1, None, 'N', auth, product,
                       ext_ref, 'N', 'Y', 'N', d, i, save_ts, save_ts, source, source]
                self.move(x, drcr, amt, ts)
                if t[5] == 'Y' and x.cust:
                    k = (x.branch, d, x.cust.no, t[4])
                    v = self.aml[k]
                    if drcr == 'D':
                        v[0] += 1
                        v[1] += lcy
                    else:
                        v[2] += 1
                        v[3] += lcy
            else:
                g = GL[x]
                row = [ref, evt_no, event, branch, x, LCY, drcr, trn, tag, None, None, money(amt), cust, cust_acct,
                       rel_ref, 'N', d, d, d, f'FY{d.year}', f'M{d.month:02d}', instrument, BANK_CODE, g[4], g[3], 'G',
                       module, self.seq, 'N', user, 1, None, 'N', auth, product, ext_ref, 'N', 'N', 'N', d, i,
                       save_ts, save_ts, source, source]
            if writer is self.daily:
                row = row + ['U', None, 'Y', 'A']
            writer.write(row)
        self.stats[trn] += 1
        return ref

    def ft_row(self, ts, ref, product, dr, cr, amt_dr, amt_cr, details, by, ben, country=None, inst=None,
               remarks=None, src='INTERNET'):
        d = ts.date()

        def side(x):
            return (x.branch, x.no, x.ccy, x.iban) if isinstance(x, Acct) else ('000', x, LCY, None)

        db, dn, dc, di = side(dr)
        cb, cn, cc, ci = side(cr)
        ccy_cr = cc if not isinstance(cr, str) else (country_ccy(country) if country else LCY)
        ccy_dr = dc if not isinstance(dr, str) else (country_ccy(country) if country else LCY)
        rate = round(CCY_RATE[ccy_dr] / CCY_RATE[ccy_cr], 6) if ccy_dr != ccy_cr else None
        self.ft.write([ref, 1, 1, product, ref, d, cb, cn, ccy_cr, amt_cr, d, rate, 'C', 'INIT', db, dn, ccy_dr,
                       amt_dr, money(amt_dr * CCY_RATE[ccy_dr]), 'S' if country else None,
                       'STANDARD' if rate else None, 'G' if country else None, src, 'Y', details[:105],
                       None, by[:105] if by else None, None, ben[:105] if ben else None, None,
                       f'COUNTRY {country}' if country and isinstance(cr, str) else None,
                       f'COUNTRY {country}' if country and isinstance(dr, str) else None, inst, di, ci, 'L', ts, d,
                       remarks])


def country_ccy(cty):
    return HOME_CCY.get(cty, 'USD') if cty != 'AE' else 'AED'


# ----------------------------------------------------------------------------- event processing
def process(E):
    while EVENTS:
        ts, _, kind, k = heapq.heappop(EVENTS)
        d = ts.date()
        a = k.get('acct')
        if a is not None and kind not in ('TD_MATURE', 'EMI') and not active(a, d):
            continue
        handler = HANDLERS[kind]
        credited = handler(E, ts, k)
        if credited is not None and credited.no in loans_pending_global:
            collect_arrears(E, ts, credited)


loans_pending_global = collections.defaultdict(list)


def collect_arrears(E, ts, a):
    q = loans_pending_global[a.no]
    while q:
        L, s = q[0]
        amt = money(s['prin'] + s['int'])
        if not E.can_debit(a, amt) or a.closed:
            return
        pay_installment(E, ts + dt.timedelta(minutes=1), L, s, a)
        q.pop(0)
    loans_pending_global.pop(a.no, None)


def pay_installment(E, ts, L, s, a):
    gl = LOAN[L['prod']][3]
    L['evt_seq'] += 1
    E.post(ts, 'LNR', [(a, 'D', money(s['prin'] + s['int']), 'TOTAL_LIQD'), (gl, 'C', s['prin'], 'PRINCIPAL_LIQD'),
                       ('310100001', 'C', s['int'], 'MAIN_INT_LIQD')],
           L['branch'], product=L['prod'], event='ALIQ', evt_no=L['evt_seq'], module='CL', rel_ref=L['no'])
    s['paid'], s['paid_amt'], s['evt'] = ts.date(), money(s['prin'] + s['int']), L['evt_seq']


def h_salary(E, ts, k):
    c, a, amt = k['cust'], k['acct'], k['amount']
    emp = c.employer
    if emp and active(emp.primary, ts.date()):
        src = emp.primary
        ref = E.post(ts, 'SAL', [(src, 'D', amt, 'TFR_AMT'), (a, 'C', amt, 'TFR_AMT')], src.branch, product='FTIN',
                     user='WPSUPLD', source='WPS')
        E.ft_row(ts, ref, 'FTIN', src, a, amt, amt, f'SALARY {ts.strftime("%b %Y").upper()}', emp.name, c.name,
                 src='WPS')
    elif c.cat == 'STAFF':
        E.post(ts, 'SAL', [('420100001', 'D', amt, 'TFR_AMT'), (a, 'C', amt, 'TFR_AMT')], '000', product='FTIN',
               user='HRPAYROLL', source='HRMS')
    else:
        ref = E.post(ts, 'SAL', [('130100001', 'D', amt, 'TFR_AMT'), (a, 'C', amt, 'TFR_AMT')], a.branch,
                     user='WPSUPLD', source='WPS')
        E.ft_row(ts, ref, 'FTIW', '130100001', a, amt, amt, f'SALARY {ts.strftime("%b %Y").upper()}',
                 c.employer_name, c.name, inst='UAE WAGE PROTECTION SYSTEM', src='WPS')
    return a


def h_ext_in(E, ts, k):
    a, amt = k['acct'], k['amount']
    lcy = money(amt * CCY_RATE[a.ccy])
    ref = E.post(ts, k['trn'], [('130100001', 'D', lcy, 'TFR_AMT'), (a, 'C', amt, 'TFR_AMT')], a.branch)
    E.ft_row(ts, ref, 'FTIL', '130100001', a, lcy, amt, k['details'], k['party'], a.cust.name,
             inst=f'{R.choice(CORP_PREFIX).upper()} BANK DEMO')
    return a


def h_ext_out(E, ts, k):
    a, amt = k['acct'], k['amount']
    if not E.can_debit(a, amt, k.get('force')):
        return None
    gl = '290100001' if k['trn'] == 'BIL' else '130100001'
    lcy = money(amt * CCY_RATE[a.ccy])
    ref = E.post(ts, k['trn'], [(a, 'D', amt, 'TFR_AMT'), (gl, 'C', lcy, 'TFR_AMT')], a.branch)
    if k['trn'] == 'FTO':
        E.ft_row(ts, ref, 'FTOL', a, '130100001', amt, lcy, k['details'], a.cust.name, k['party'],
                 inst=f'{R.choice(CORP_PREFIX).upper()} BANK DEMO')
    return None


def h_swift_in(E, ts, k):
    a, amt, cty = k['acct'], k['amount'], k['country']
    lcy = money(amt * CCY_RATE[a.ccy])
    ref = E.post(ts, 'SWI', [('120100001', 'D', lcy, 'TFR_AMT'), (a, 'C', amt, 'TFR_AMT')], a.branch,
                 ext_ref=E.ext('SWI'))
    fccy = country_ccy(cty)
    E.ft_row(ts, ref, 'FTIS', '120100001', a, money(lcy / CCY_RATE[fccy]), amt, k['details'], k['party'], a.cust.name,
             country=cty, inst=f'CORRESPONDENT BANK {cty} DEMO', src='SWIFT')
    return a


def h_swift_out(E, ts, k):
    a, amt, cty = k['acct'], k['amount'], k['country']
    if not E.can_debit(a, amt):
        return None
    lcy = money(amt * CCY_RATE[a.ccy])
    ref = E.post(ts, 'SWO', [(a, 'D', amt, 'TFR_AMT'), ('120100001', 'C', lcy, 'TFR_AMT')], a.branch,
                 ext_ref=E.ext('SWO'))
    fccy = country_ccy(cty)
    E.ft_row(ts, ref, 'FTOS', a, '120100001', amt, money(lcy / CCY_RATE[fccy]), k['details'], a.cust.name, k['party'],
             country=cty, inst=f'BENEFICIARY BANK {cty} DEMO')
    fee_lcy = 52.5 if a.cust.type == 'C' else 26.25
    fee = money(fee_lcy / CCY_RATE[a.ccy])
    if E.can_debit(a, fee):
        E.post(ts + dt.timedelta(seconds=5), 'CHG', [(a, 'D', fee, 'CHARGE'),
                                                     ('320100001', 'C', money(fee * CCY_RATE[a.ccy]), 'CHARGE')],
               a.branch, event='CHRG', module='FT', ref=ref)
    return None


def h_cash_in(E, ts, k):
    a, amt = k['acct'], k['amount']
    br = k.get('branch') or a.branch
    gl = '110200001' if k['trn'] == 'CDM' else '110100001'
    E.post(ts, k['trn'], [(gl, 'D', money(amt * CCY_RATE[a.ccy]), 'TXN_AMT'), (a, 'C', amt, 'TXN_AMT')], br,
           user='SWITCH' if k['trn'] == 'CDM' else None)
    return a


def h_cash_out(E, ts, k):
    a, amt = k['acct'], k['amount']
    if not E.can_debit(a, amt):
        return None
    E.post(ts, 'CSW', [(a, 'D', amt, 'TXN_AMT'), ('110100001', 'C', money(amt * CCY_RATE[a.ccy]), 'TXN_AMT')],
           R.choice([b[0] for b in BRANCHES[1:]]))
    return None


def h_cheque_in(E, ts, k):
    a, amt = k['acct'], k['amount']
    E.post(ts, 'CHD', [('130200001', 'D', money(amt * CCY_RATE[a.ccy]), 'TXN_AMT'), (a, 'C', amt, 'TXN_AMT')], a.branch,
           instrument=digits(6))
    return a


def h_cheque_out(E, ts, k):
    a, amt = k['acct'], k['amount']
    if not E.can_debit(a, amt):
        E.stats['CHQ_RETURNED'] += 1
        return None
    E.post(ts, 'CHQ', [(a, 'D', amt, 'TXN_AMT'), ('130200001', 'C', money(amt * CCY_RATE[a.ccy]), 'TXN_AMT')], a.branch,
           instrument=digits(6))
    return None


def h_book(E, ts, k):
    s, t, amt = k['src'], k['dst'], k['amount']
    if not active(t, ts.date()) or not E.can_debit(s, amt):
        return None
    ref = E.post(ts, 'BKT', [(s, 'D', amt, 'TFR_AMT'), (t, 'C', amt, 'TFR_AMT')], s.branch)
    E.ft_row(ts, ref, 'FTIN', s, t, amt, amt, k['details'], s.cust.name, t.cust.name)
    return t


_terms = {}


def card_meta(k, branch):
    trn = k['trn']
    foreign = k.get('foreign')
    if trn == 'ATM':
        on_us = R.random() < .55 or k.get('atm_branch')
        br = k.get('atm_branch') or (branch if R.random() < .6 else R.choice([b[0] for b in BRANCHES]))
        city = next(b[2] for b in BRANCHES if b[0] == br)
        return (6011, 'ATM ' + (BANK_NAME.upper() if on_us else 'NETWORK'), city, 'AE', 'AED'), ('ATM' + br + (
            '01' if on_us else '77'))
    mcc = 5999 if trn == 'ECM' else R.choices(list(MERCHANTS), [30, 18, 10, 9, 6, 3, 5, 4, 6, 1, 1, 3, 0, 2, 1, 1])[0]
    if foreign:
        cty, city, ccy = foreign
        if trn == 'POS':
            mcc = R.choice([5812, 5411, 7011, 5651, 4121, 5311])
    else:
        cty, city, ccy = 'AE', R.choice(UAE_CITIES), 'AED'
    if trn == 'ECM' and not foreign and R.random() < .25:
        mcc = R.choice([4511, 7011, 4814, 7832])
    cat, names = MERCHANTS[mcc]
    name = R.choice(names)
    tid = _terms.setdefault((name, city), f'T{len(_terms) + 10000000:07d}')
    return (mcc, name, city, cty, ccy), tid


def h_card(E, ts, k):
    c, a, amt, trn = k['cust'], k['acct'], k['amount'], k['trn']
    card = c.cards[0] if c.cards else None
    if not card or ts.date() < card['issued']:
        return None
    (mcc, mname, city, cty, ccy), tid = card_meta(k, a.branch)
    ok = E.can_debit(a, amt)
    ext = E.ext({'ATM': 'ATM', 'POS': 'POS', 'ECM': 'ECM'}[trn])
    txn_amt = amt if ccy == 'AED' else money(amt / CCY_RATE[ccy] / 1.0275)       # 2.75 percent FX markup
    stan = digits(6)
    E.sw.write(['0200', card['pan'], a.branch, a.no, trn, '010000' if trn == 'ATM' else '000000', txn_amt,
                CCY_NUM[ccy], amt, '784', amt, '784', ts.date(), ts.strftime('%H%M%S'), stan,
                '400000' if trn != 'ATM' else '099000', tid, f'{tid}MID'[:15], f'M{stable(mname) % 10**9:09d}',
                mname[:40], city[:40], cty, mcc, digits(12), digits(6) if ok else None, 0 if ok else 51,
                'Y' if cty == 'AE' else 'N', '190100001', 'VISA' if trn != 'ATM' else 'UAESWITCH', 'S' if ok else 'F',
                {'ATM': 'ATM', 'POS': 'POS', 'ECM': 'ECM'}[trn], ext, ext])
    if not ok:
        E.stats['CARD_DECLINED'] += 1
        return None
    gl = '110200001' if (trn == 'ATM' and 'NETWORK' not in mname) else '190100001'
    E.post(ts, trn, [(a, 'D', amt, 'TXN_AMT'), (gl, 'C', amt, 'TXN_AMT')], a.branch, ext_ref=ext, source='SWITCH')
    return None


def h_monthend(E, ts, k):
    a = k['acct']
    if a.closed or a.bal <= 0 and a.kind == 'S':
        return None
    if a.cls in ('SAVIND', 'PRISAV') and a.bal > 0:
        rate = .75 if a.cls == 'SAVIND' else 2.0
        intr = money(a.bal * rate / 1200)
        if intr >= .01:
            E.post(ts, 'INT', [('410100001', 'D', intr, 'INTEREST'), (a, 'C', intr, 'INTEREST')], a.branch,
                   event='ILIQ', module='IC')
    elif a.cls == 'CURIND' and a.bal < 3000 and E.can_debit(a, 26.25):
        E.post(ts, 'CHG', [(a, 'D', 26.25, 'CHARGE'), ('320100001', 'C', 26.25, 'CHARGE')], a.branch, event='CHRG')
    elif a.cls in ('CURSME', 'CURCOR'):
        fee = 105.0 if a.cls == 'CURSME' else 262.5
        E.post(ts, 'CHG', [(a, 'D', fee, 'CHARGE'), ('320100001', 'C', fee, 'CHARGE')], a.branch, event='CHRG')
    return None


def h_dsbr(E, ts, k):
    L = k['loan']
    a = L['acct']
    gl = LOAN[L['prod']][3]
    E.post(ts, 'LND', [(gl, 'D', L['amount'], 'PRINCIPAL_DSBR'), (a, 'C', L['amount'], 'PRINCIPAL_DSBR')],
           L['branch'], product=L['prod'], event='DSBR', evt_no=1, module='CL', rel_ref=L['no'])
    if L['prod'] in ('ALN1', 'HLN1'):
        payee = 'Prime Motors Demo LLC' if L['prod'] == 'ALN1' else f'{R.choice(CORP_PREFIX)} Developers LLC'
        h_ext_out(E, ts + dt.timedelta(minutes=30), {'acct': a, 'amount': L['amount'], 'trn': 'FTO',
                                                       'party': payee, 'details': 'LOAN PROCEEDS TO SELLER'})
    return a


def h_emi(E, ts, k):
    L, s = k['loan'], k['inst']
    a = L['acct']
    amt = money(s['prin'] + s['int'])
    q = loans_pending_global[a.no]
    if not q and E.can_debit(a, amt) and not a.closed:
        pay_installment(E, ts, L, s, a)
    else:
        q.append((L, s))
    return None


def h_drain(E, ts, k):
    a = k['acct']
    amt = money(max(0, a.bal) * k['share'], 0)
    if amt > 100:
        h_ext_out(E, ts, {'acct': a, 'amount': amt, 'trn': 'FTO', 'party': a.cust.name,
                          'details': 'TRANSFER TO OWN ACCOUNT OTHER BANK'})
    return None


def h_close(E, ts, k):
    c = k['cust']
    for a in c.accounts:
        if a.kind == 'T' or a.closed:
            continue
        if a.bal > 0:
            h_ext_out(E, ts, {'acct': a, 'amount': money(a.bal), 'trn': 'FTO', 'party': c.name,
                              'details': 'ACCOUNT CLOSURE PROCEEDS'})
        if abs(a.bal) < .01:
            a.closed = ts.date()
    for card in c.cards:
        card['status'] = 'C'
    return None


def h_td_book(E, ts, k):
    a, src = k['acct'], k['src']
    amt = a.td['amount']
    force = not E.can_debit(src, amt)
    if force:   # fund from an external transfer first, as customers do
        h_ext_in(E, ts - dt.timedelta(minutes=20), {'acct': src, 'amount': amt, 'trn': 'FTI',
                                                     'party': a.cust.name, 'details': 'OWN FUNDS FOR DEPOSIT'})
    E.post(ts, 'TDF', [(src, 'D', amt, 'TFR_AMT'), (a, 'C', amt, 'TFR_AMT')], a.branch, event='BOOK')
    return None


def h_td_mature(E, ts, k):
    a = k['acct']
    t = a.td
    if a.closed or a.bal <= 0:
        return None
    intr = money(a.bal * t['rate'] / 100 * t['tenor'] / 12)
    E.post(ts, 'INT', [('410100001', 'D', intr, 'INTEREST'), (a, 'C', intr, 'INTEREST')], a.branch, event='ILIQ')
    if not t['rollover']:
        dst = a.cust.primary
        amt = a.bal
        E.post(ts + dt.timedelta(seconds=10), 'TDM', [(a, 'D', amt, 'TFR_AMT'), (dst, 'C', amt, 'TFR_AMT')],
               a.branch, event='MATR')
        a.closed = ts.date()
        return dst
    return None


HANDLERS = {'SALARY': h_salary, 'EXT_IN': h_ext_in, 'EXT_OUT': h_ext_out, 'SWIFT_IN': h_swift_in,
            'SWIFT_OUT': h_swift_out, 'CASH_IN': h_cash_in, 'CASH_OUT': h_cash_out, 'CHEQUE_IN': h_cheque_in,
            'CHEQUE_OUT': h_cheque_out, 'BOOK': h_book, 'CARD': h_card, 'MONTHEND': h_monthend, 'DSBR': h_dsbr,
            'EMI': h_emi, 'DRAIN': h_drain, 'CLOSE': h_close, 'TD_BOOK': h_td_book, 'TD_MATURE': h_td_mature}


# ----------------------------------------------------------------------------- static tables
AUD = {'RECORD_STAT': 'O', 'AUTH_STAT': 'A', 'ONCE_AUTH': 'Y', 'MOD_NO': 1, 'MAKER_ID': 'SYSTEM',
       'CHECKER_ID': 'SYSTEM'}


def aud(d, maker='SYSTEM', checker='SYSTEM'):
    t = dt.datetime(d.year, d.month, d.day, 9, R.randint(0, 59))
    return dict(AUD, MAKER_ID=maker, CHECKER_ID=checker, MAKER_DT_STAMP=t, CHECKER_DT_STAMP=t + dt.timedelta(minutes=R.randint(5, 240)))


def write_static(out):
    w = TableWriter(out, 'STTM_BANK', ['BANK_CODE', 'BANK_NAME', 'HO_BRANCH', 'HO_CURRENCY', 'REPORTING_CURRENCY',
                                        'CIF_MASK', 'CUSTOMER_ACC_MASK', 'GL_MASK', 'AUTO_GEN_CIF'] + list(AUD) +
                    ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    w.write(dict(BANK_CODE=BANK_CODE, BANK_NAME=BANK_NAME, HO_BRANCH='000', HO_CURRENCY=LCY, REPORTING_CURRENCY=LCY,
                 CIF_MASK='bbbnnnnnn', CUSTOMER_ACC_MASK='bbbttnnnnnnnn', GL_MASK='nnnnnnnnn', AUTO_GEN_CIF='Y',
                 **aud(dt.date(2008, 1, 1))))
    w.close()
    w = TableWriter(out, 'STTM_BRANCH', ['BRANCH_CODE', 'BRANCH_NAME', 'BRANCH_ADDR1', 'BRANCH_ADDR2', 'BRANCH_ADDR3',
                                          'PARENT_BRANCH', 'REGIONAL_OFFICE', 'BANK_CODE', 'COUNTRY_CODE', 'BRANCH_LCY',
                                          'SWIFT_ADDR', 'CURRENT_CYCLE', 'CURRENT_PERIOD', 'WEEK_HOL1', 'WEEK_HOL2',
                                          'IBAN_CNTRY_CD', 'GMT_HOURS', 'GMT_MINS', 'GMT_AHEAD', 'CB_DORMANCY_DAYS',
                                          'TIME_LEVEL', 'END_OF_INPUT'] + list(AUD) + ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    for code, name, emirate, area in BRANCHES:
        w.write(dict(BRANCH_CODE=code, BRANCH_NAME=name, BRANCH_ADDR1=f'{area} Street', BRANCH_ADDR2=area,
                     BRANCH_ADDR3=f'{emirate}, UAE', PARENT_BRANCH='000', REGIONAL_OFFICE='000' if emirate in (
                         'Dubai', 'Sharjah', 'Ajman', 'Ras Al Khaimah', 'Fujairah') else '005', BANK_CODE=BANK_CODE,
                     COUNTRY_CODE='AE', BRANCH_LCY=LCY, SWIFT_ADDR=f'OADBAEAD{code}', CURRENT_CYCLE=f'FY{TODAY.year}',
                     CURRENT_PERIOD=f'M{TODAY.month:02d}', WEEK_HOL1='6', WEEK_HOL2='7', IBAN_CNTRY_CD='AE',
                     GMT_HOURS=4, GMT_MINS=0, GMT_AHEAD='Y', CB_DORMANCY_DAYS=365, TIME_LEVEL=0, END_OF_INPUT='N',
                     **aud(dt.date(2008, 1, 1))))
    w.close()
    w = TableWriter(out, 'STTM_COUNTRY', ['COUNTRY_CODE', 'DESCRIPTION', 'REGION_CODE', 'BLACKLISTED',
                                           'ISO_NUM_COUNTRY_CODE', 'IBAN_CHECK_REQD'] + list(AUD) +
                    ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    for iso, name, reg, bl, num in COUNTRIES:
        w.write(dict(COUNTRY_CODE=iso, DESCRIPTION=name, REGION_CODE=reg, BLACKLISTED=bl, ISO_NUM_COUNTRY_CODE=num,
                     IBAN_CHECK_REQD='Y' if iso in ('AE', 'SA', 'GB', 'FR', 'DE', 'JO', 'EG', 'PK', 'TR') else 'N',
                     **aud(dt.date(2008, 1, 1))))
    w.close()
    w = TableWriter(out, 'CYTM_CCY_DEFN_MASTER', ['CCY_CODE', 'CCY_NAME', 'COUNTRY', 'CCY_DECIMALS', 'CCY_ROUND_RULE',
                                                   'CCY_ROUND_UNIT', 'CCY_FORMAT_MASK', 'CCY_SPOT_DAYS',
                                                   'CCY_INT_METHOD', 'MAINTENANCE_COUNTRY', 'POSITION_GL',
                                                   'POSITION_EQVGL'] + list(AUD) + ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    for code, name, cty, dec, num, rate in CURRENCIES:
        w.write(dict(CCY_CODE=code, CCY_NAME=name, COUNTRY=cty, CCY_DECIMALS=dec, CCY_ROUND_RULE='R',
                     CCY_ROUND_UNIT=float(10 ** -dec), CCY_FORMAT_MASK='I', CCY_SPOT_DAYS=2,
                     CCY_INT_METHOD=2 if code in ('AED', 'GBP', 'INR', 'PKR', 'OMR', 'SAR') else 1,
                     MAINTENANCE_COUNTRY='AE', POSITION_GL=None, POSITION_EQVGL=None, **aud(dt.date(2008, 1, 1))))
    w.close()
    w = TableWriter(out, 'CYTM_RATES_MASTER', ['BRANCH_CODE', 'CCY1', 'CCY2'] + list(AUD) +
                    ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    for code, *_ in CURRENCIES:
        if code != LCY:
            w.write(dict(BRANCH_CODE='000', CCY1=code, CCY2=LCY, **aud(dt.date(2008, 1, 1))))
    w.close()
    w = TableWriter(out, 'STTM_CUSTOMER_CAT', ['CUST_CAT', 'CUST_CAT_DESC'] + list(AUD) +
                    ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    for code, desc in CUSTOMER_CATEGORIES:
        w.write(dict(CUST_CAT=code, CUST_CAT_DESC=desc, **aud(dt.date(2008, 1, 1))))
    w.close()
    w = TableWriter(out, 'STTM_ACCOUNT_CLASS', ['ACCOUNT_CLASS', 'DESCRIPTION', 'AC_CLASS_TYPE', 'DORMANCY',
                                                 'ACC_STMT_TYPE', 'ACC_STMT_CYCLE', 'STATEMENT_DAY', 'ACCOUNT_CODE',
                                                 'DR_GL_LINE', 'CR_GL_LINE', 'OVERDRAFT_FACILITY', 'IC_INCLUSION',
                                                 'IBAN_REQUIRED', 'DIRECT_BANKING', 'RECORD_STAT', 'AUTH_STAT',
                                                 'ONCE_AUTH', 'MAKER_ID', 'CHECKER_ID'])
    for cls, desc, typ, gl, dorm, mb in ACCOUNT_CLASSES:
        w.write(dict(ACCOUNT_CLASS=cls, DESCRIPTION=desc, AC_CLASS_TYPE=typ, DORMANCY=dorm or None, ACC_STMT_TYPE='D',
                     ACC_STMT_CYCLE='M', STATEMENT_DAY=31, ACCOUNT_CODE=TYPECODE[cls], DR_GL_LINE=gl, CR_GL_LINE=gl,
                     OVERDRAFT_FACILITY='Y' if cls in ('CURSME', 'CURCOR') else 'N', IC_INCLUSION='Y',
                     IBAN_REQUIRED='Y', DIRECT_BANKING='Y', RECORD_STAT='O', AUTH_STAT='A', ONCE_AUTH='Y',
                     MAKER_ID='SYSTEM', CHECKER_ID='SYSTEM'))
    w.close()
    w = TableWriter(out, 'STTM_TRN_CODE', ['TRN_CODE', 'TRN_DESC', 'AVL_INFO', 'CHEQUE_MANDATORY', 'IC_TXN_COUNT',
                                            'CONSIDER_FOR_ACTIVITY', 'AML_MONITORING', 'PRODUCT_CAT', 'SALARY_CREDIT',
                                            'AVAIL_BAL_REQD'] + list(AUD) + ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    for code, desc, mod, prod, cat, aml, sal in TRN_CODES:
        w.write(dict(TRN_CODE=code, TRN_DESC=desc, AVL_INFO='Y', CHEQUE_MANDATORY='Y' if code in ('CHQ', 'CHD') else 'N',
                     IC_TXN_COUNT='Y', CONSIDER_FOR_ACTIVITY='N' if code in ('INT', 'CHG') else 'Y',
                     AML_MONITORING=aml, PRODUCT_CAT=cat, SALARY_CREDIT=sal, AVAIL_BAL_REQD='Y',
                     **aud(dt.date(2008, 1, 1))))
    w.close()
    w = TableWriter(out, 'GLTM_GLMASTER', ['GL_CODE', 'GL_DESC', 'PARENT_GL', 'ULTI_PARENT', 'LEAF', 'TYPE',
                                            'CUSTOMER', 'CATEGORY', 'CCY_RES', 'BLOCK', 'POSTING_RES', 'REVAL',
                                            'AC_STMT_REQUIRED'] + list(AUD) + ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    for code, desc, parent, cat, typ, cust in GLS:
        w.write(dict(GL_CODE=code, GL_DESC=desc, PARENT_GL=parent, ULTI_PARENT=parent if parent != '0' else code,
                     LEAF='N' if parent == '0' else 'Y', TYPE=typ, CUSTOMER=cust, CATEGORY=cat, CCY_RES='N',
                     BLOCK='N', POSTING_RES='N', REVAL='N', AC_STMT_REQUIRED='N', **aud(dt.date(2008, 1, 1))))
    w.close()
    w = TableWriter(out, 'CLTM_PRODUCT', ['PRODUCT_CODE', 'PRODUCT_DESC', 'PRODUCT_CATEGORY', 'MIN_TENOR', 'STD_TENOR',
                                           'MAX_TENOR', 'TENOR_UNIT', 'LIQUIDATION_MODE', 'RATE_TYPE', 'MODULE_CODE',
                                           'RECORD_STAT', 'AUTH_STAT', 'ONCE_AUTH', 'MOD_NO', 'MAKER_ID',
                                           'MAKER_DT_STAMP', 'CHECKER_ID', 'CHECKER_DT_STAMP', 'RESCH_ALLOW',
                                           'USE_GUARANTOR'])
    for code, desc, cat, gl, (rl, rh), (tl, th) in LOAN_PRODUCTS:
        a = aud(dt.date(2010, 1, 1))
        w.write(dict(PRODUCT_CODE=code, PRODUCT_DESC=desc, PRODUCT_CATEGORY=cat, MIN_TENOR=tl, STD_TENOR=th,
                     MAX_TENOR=th, TENOR_UNIT='M', LIQUIDATION_MODE='A', RATE_TYPE='STANDARD', MODULE_CODE='CL',
                     RECORD_STAT='O', AUTH_STAT='A', ONCE_AUTH='Y', MOD_NO=1, MAKER_ID='SYSTEM',
                     MAKER_DT_STAMP=a['MAKER_DT_STAMP'], CHECKER_ID='SYSTEM', CHECKER_DT_STAMP=a['CHECKER_DT_STAMP'],
                     RESCH_ALLOW='Y', USE_GUARANTOR='Y' if code in ('PLN1', 'SLN1') else 'N'))
    w.close()


def write_customers(out):
    cw = TableWriter(out, 'STTM_CUSTOMER', [
        'CUSTOMER_NO', 'CUSTOMER_TYPE', 'CUSTOMER_NAME1', 'FULL_NAME', 'SHORT_NAME', 'ADDRESS_LINE1', 'ADDRESS_LINE2',
        'ADDRESS_LINE3', 'ADDRESS_LINE4', 'COUNTRY', 'NATIONALITY', 'LANGUAGE', 'EXPOSURE_COUNTRY', 'LOCAL_BRANCH',
        'UNIQUE_ID_NAME', 'UNIQUE_ID_VALUE', 'FROZEN', 'DECEASED', 'WHEREABOUTS_UNKNOWN', 'CUSTOMER_CATEGORY',
        'CREDIT_RATING', 'LIMIT_CCY', 'RISK_PROFILE', 'RISK_CATEGORY', 'AML_REQUIRED', 'CUST_CLASSIFICATION',
        'CIF_STATUS', 'CIF_CREATION_DATE', 'KYC_DETAILS', 'STAFF', 'KYC_REF_NO', 'PRIVATE_CUSTOMER', 'RM_ID',
        'FREQUENCY', 'STMT_DAY', 'PINCODE', 'SANCTIONS_CHECKS_REQUIRED', 'TAXID_NO', 'CRS_TYPE', 'TAX_CNTRY'] +
        list(AUD) + ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    pw = TableWriter(out, 'STTM_CUST_PERSONAL', [
        'CUSTOMER_NO', 'CUSTOMER_PREFIX', 'FIRST_NAME', 'MIDDLE_NAME', 'LAST_NAME', 'DATE_OF_BIRTH', 'MINOR', 'SEX',
        'P_NATIONAL_ID', 'PASSPORT_NO', 'PPT_ISS_DATE', 'PPT_EXP_DATE', 'D_ADDRESS1', 'D_ADDRESS2', 'D_ADDRESS3',
        'D_COUNTRY', 'P_ADDRESS1', 'P_COUNTRY', 'RESIDENT_STATUS', 'MOBILE_NUMBER', 'MOB_ISD_NO', 'E_MAIL',
        'PLACE_OF_BIRTH', 'BIRTH_COUNTRY', 'CUST_COMM_MODE', 'D_PINCODE'])
    dw = TableWriter(out, 'STTM_CUST_DOMESTIC', ['CUSTOMER_NO', 'MARITAL_STATUS', 'SPOUSE_NAME', 'DEPENDENT_CHILDREN',
                                                  'DEPENDENT_OTHERS', 'ACCOMODATION'])
    kw = TableWriter(out, 'STTM_CUST_CORPORATE', ['CUSTOMER_NO', 'CORPORATE_NAME', 'C_NATIONAL_ID', 'R_ADDRESS1',
                                                   'R_ADDRESS2', 'R_ADDRESS3', 'INCORP_DATE', 'CAPITAL', 'NETWORTH',
                                                   'BUSINESS_DESCRIPTION', 'INCORP_COUNTRY', 'R_COUNTRY', 'AMOUNTS_CCY',
                                                   'OWNERSHIP_TYPE'])
    km = TableWriter(out, 'STTM_KYC_MASTER', ['KYC_REF_NO', 'KYC_DESC', 'KYC_CUST_TYPE', 'RISK_LEVEL', 'CRS_TYPE'] +
                     list(AUD) + ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    kr = TableWriter(out, 'STTM_KYC_RETAIL', [
        'KYC_REF_NO', 'DECLARED', 'PEP', 'PEP_REMARKS', 'RESIDENT', 'LOCAL_ADDR', 'HOME_COUNTRY_ADDR', 'BIRTH_DATE',
        'BIRTH_PLACE', 'NATIONALITY', 'PASSPORT_NO', 'PASSPORT_EXPIRY_DATE', 'VISA_NUMBER', 'VISA_EXPIRY_DATE',
        'MOBILE_TEL_NO', 'SALARY_INCOME', 'RENTAL_INCOME', 'INVESTMENT_INCOME', 'BUSINESS_INCOME', 'TOTAL_INCOME',
        'TOTAL_NET_WORTH', 'ACC_PURPOSE', 'ACC_TYPE', 'KYC_NXT_REVIEW_DATE', 'KYC_COMMENTS', 'KYC_AMTS_CCY',
        'BIRTH_COUNTRY', 'LOCAL_ADDR_COUNTRY', 'HOME_ADDR_COUNTRY', 'MOB_ISD_NO'])
    sg = TableWriter(out, 'STTM_CREDIT_SCORE_GRADE', ['CUSTOMER_NO', 'RULE_ID', 'GRADE', 'FINAL_SCORE', 'SERIAL_NUMBER',
                                                       'CONTEXT'])
    risk_txt = {'Level1': 'LOW', 'Level2': 'MEDIUM', 'Level3': 'HIGH'}
    for c in CUSTS:
        kyc = f'KYC{c.no}'
        a = aud(c.cif_date, maker=f'OPS{c.branch}', checker=f'CHK{c.branch}')
        level = c.kyc_level
        if c.scen & {'AML_STRUCTURING', 'AML_PASS_THROUGH', 'AML_MONEY_MULE'} and R.random() < .3:
            level = 'Level2'       # some scenario customers were already medium risk; most look ordinary
        if c.type == 'I':
            grade = 'A' if c.score >= 780 else 'B' if c.score >= 720 else 'C' if c.score >= 660 else 'D' if c.score >= 600 else 'E'
            cw.write(dict(CUSTOMER_NO=c.no, CUSTOMER_TYPE='I', CUSTOMER_NAME1=c.name.upper()[:105], FULL_NAME=c.name,
                          SHORT_NAME=c.short, ADDRESS_LINE1=f'Flat {R.randint(101, 2405)}, {c.area}',
                          ADDRESS_LINE2=c.area, ADDRESS_LINE3=c.emirate, ADDRESS_LINE4='UNITED ARAB EMIRATES',
                          COUNTRY='AE', NATIONALITY=c.nat, LANGUAGE='ARA' if c.nat in ('AE', 'SA', 'EG', 'JO', 'LB', 'SY') else 'ENG',
                          EXPOSURE_COUNTRY='AE', LOCAL_BRANCH=c.branch, UNIQUE_ID_NAME='EMIRATES ID',
                          UNIQUE_ID_VALUE=c.eid, FROZEN='N', DECEASED='N', WHEREABOUTS_UNKNOWN='N',
                          CUSTOMER_CATEGORY=c.cat, CREDIT_RATING=grade, LIMIT_CCY='AED', RISK_PROFILE=risk_txt[level],
                          RISK_CATEGORY=risk_txt[level][0], AML_REQUIRED='Y',
                          CUST_CLASSIFICATION='PRIORITY' if c.cat == 'PRIORITY' else 'RETAIL', CIF_STATUS='NORM',
                          CIF_CREATION_DATE=c.cif_date, KYC_DETAILS='Y', STAFF='Y' if c.cat == 'STAFF' else 'N',
                          KYC_REF_NO=kyc, PRIVATE_CUSTOMER='N', RM_ID=c.rm, FREQUENCY='M', STMT_DAY='31',
                          PINCODE=f'PO BOX {R.randint(1000, 99999)}', SANCTIONS_CHECKS_REQUIRED='Y', TAXID_NO=None,
                          CRS_TYPE='INDIVIDUAL', TAX_CNTRY='AE', **a))
            pw.write(dict(CUSTOMER_NO=c.no, CUSTOMER_PREFIX='MR' if c.sex == 'M' else ('MRS' if c.married else 'MS'),
                          FIRST_NAME=c.first, MIDDLE_NAME=c.middle or None, LAST_NAME=c.last, DATE_OF_BIRTH=c.dob,
                          MINOR='N', SEX=c.sex, P_NATIONAL_ID=c.eid, PASSPORT_NO=c.passport,
                          PPT_ISS_DATE=add_months(c.passport_exp, -120), PPT_EXP_DATE=c.passport_exp,
                          D_ADDRESS1=f'Flat {R.randint(101, 2405)}', D_ADDRESS2=c.area, D_ADDRESS3=c.emirate,
                          D_COUNTRY='AE', P_ADDRESS1=f'{dict((x[0], x[1]) for x in COUNTRIES)[c.nat]}', P_COUNTRY=c.nat,
                          RESIDENT_STATUS='R', MOBILE_NUMBER=c.mobile, MOB_ISD_NO=971, E_MAIL=c.email,
                          PLACE_OF_BIRTH=dict((x[0], x[1]) for x in COUNTRIES)[c.nat].title(), BIRTH_COUNTRY=c.nat,
                          CUST_COMM_MODE='E', D_PINCODE=f'PO BOX {R.randint(1000, 99999)}'))
            dw.write(dict(CUSTOMER_NO=c.no, MARITAL_STATUS='M' if c.married else 'S',
                          SPOUSE_NAME=None, DEPENDENT_CHILDREN=c.children, DEPENDENT_OTHERS=R.choice([0, 0, 0, 1, 2]),
                          ACCOMODATION='R' if c.rent else R.choice(['O', 'C', 'F'])))
            declared = c.salary * 12 if c.salary else 0
            km.write(dict(KYC_REF_NO=kyc, KYC_DESC=f'KYC {c.name}'[:255], KYC_CUST_TYPE='R', RISK_LEVEL=level,
                          CRS_TYPE='INDIVIDUAL', **a))
            kr.write(dict(KYC_REF_NO=kyc, DECLARED='Y', PEP='Y' if c.pep else 'N',
                          PEP_REMARKS='Senior public function, enhanced due diligence' if c.pep else None,
                          RESIDENT='Y', LOCAL_ADDR=f'{c.area}, {c.emirate}', HOME_COUNTRY_ADDR=None, BIRTH_DATE=c.dob,
                          BIRTH_PLACE=dict((x[0], x[1]) for x in COUNTRIES)[c.nat].title(), NATIONALITY=c.nat,
                          PASSPORT_NO=c.passport, PASSPORT_EXPIRY_DATE=c.passport_exp,
                          VISA_NUMBER=None if c.nat == 'AE' else f'201/{c.cif_date.year}/{digits(7)}',
                          VISA_EXPIRY_DATE=c.visa_exp, MOBILE_TEL_NO=c.mobile,
                          SALARY_INCOME='Y' if c.income_src in ('SALARY', 'PENSION') else 'N', RENTAL_INCOME='N',
                          INVESTMENT_INCOME='Y' if c.cat == 'PRIORITY' else 'N',
                          BUSINESS_INCOME='Y' if c.income_src == 'BUSINESS' else 'N', TOTAL_INCOME=money(declared, 0),
                          TOTAL_NET_WORTH=money(declared * R.uniform(.5, 8) + (2e6 if c.cat == 'PRIORITY' else 0), -3),
                          ACC_PURPOSE={'SALARY': 'SALARY', 'PENSION': 'PENSION', 'BUSINESS': 'BUSINESS PROCEEDS',
                                       'FAMILY': 'SAVINGS'}[c.income_src],
                          ACC_TYPE=c.primary.cls, KYC_NXT_REVIEW_DATE=c.kyc_review,
                          KYC_COMMENTS=f'Occupation: {c.occ}; Employer: {c.employer_name or "N/A"}'[:255],
                          KYC_AMTS_CCY='AED', BIRTH_COUNTRY=c.nat, LOCAL_ADDR_COUNTRY='AE', HOME_ADDR_COUNTRY=c.nat,
                          MOB_ISD_NO=971))
            sg.write(dict(CUSTOMER_NO=c.no, RULE_ID='BUREAU_SCORE', GRADE=grade, FINAL_SCORE=c.score, SERIAL_NUMBER=1,
                          CONTEXT='External bureau score at last refresh'))
        else:
            cw.write(dict(CUSTOMER_NO=c.no, CUSTOMER_TYPE='C', CUSTOMER_NAME1=c.name.upper(), FULL_NAME=c.name,
                          SHORT_NAME=c.short, ADDRESS_LINE1=f'Office {R.randint(101, 3909)}, {c.area}',
                          ADDRESS_LINE2=c.area, ADDRESS_LINE3=c.emirate, ADDRESS_LINE4='UNITED ARAB EMIRATES',
                          COUNTRY='AE', NATIONALITY='AE', LANGUAGE='ENG', EXPOSURE_COUNTRY='AE', LOCAL_BRANCH=c.branch,
                          UNIQUE_ID_NAME='TRADE LICENSE', UNIQUE_ID_VALUE=c.license, FROZEN='N', DECEASED='N',
                          WHEREABOUTS_UNKNOWN='N', CUSTOMER_CATEGORY=c.cat, CREDIT_RATING=str(c.score),
                          LIMIT_CCY='AED', RISK_PROFILE=risk_txt[level], RISK_CATEGORY=risk_txt[level][0],
                          AML_REQUIRED='Y', CUST_CLASSIFICATION=c.cat, CIF_STATUS='NORM', CIF_CREATION_DATE=c.cif_date,
                          KYC_DETAILS='Y', STAFF='N', KYC_REF_NO=kyc, PRIVATE_CUSTOMER='N', RM_ID=c.rm, FREQUENCY='M',
                          STMT_DAY='31', PINCODE=f'PO BOX {R.randint(1000, 99999)}', SANCTIONS_CHECKS_REQUIRED='Y',
                          TAXID_NO=c.trn, CRS_TYPE='ENTITY', TAX_CNTRY='AE', **a))
            kw.write(dict(CUSTOMER_NO=c.no, CORPORATE_NAME=c.name, C_NATIONAL_ID=c.license,
                          R_ADDRESS1=f'Office {R.randint(101, 3909)}', R_ADDRESS2=c.area, R_ADDRESS3=c.emirate,
                          INCORP_DATE=c.incorp, CAPITAL=money(max(1e5, c.turnover * R.uniform(.02, .1)), -3),
                          NETWORTH=money(c.turnover * R.uniform(.05, .4), -3), BUSINESS_DESCRIPTION=c.sector[1],
                          INCORP_COUNTRY='AE', R_COUNTRY='AE', AMOUNTS_CCY='AED',
                          OWNERSHIP_TYPE={'LLC': 'LIMITED LIABILITY COMPANY', 'FZE': 'FREE ZONE ESTABLISHMENT',
                                          'FZCO': 'FREE ZONE COMPANY', 'Est.': 'SOLE ESTABLISHMENT'}[c.legal]))
            km.write(dict(KYC_REF_NO=kyc, KYC_DESC=f'KYC {c.name} {c.sector[0]}'[:255], KYC_CUST_TYPE='C',
                          RISK_LEVEL=level, CRS_TYPE='ENTITY', **a))
            sg.write(dict(CUSTOMER_NO=c.no, RULE_ID='INTERNAL_RATING', GRADE=f'RR{c.score:02d}', FINAL_SCORE=c.score,
                          SERIAL_NUMBER=1, CONTEXT=f'Obligor risk rating, annual turnover AED {c.turnover:,.0f}'))
    for w in (cw, pw, dw, kw, km, kr, sg):
        w.close()


def write_accounts(out, E):
    aw = TableWriter(out, 'STTM_CUST_ACCOUNT', [
        'BRANCH_CODE', 'CUST_AC_NO', 'AC_DESC', 'CUST_NO', 'CCY', 'ACCOUNT_CLASS', 'AC_STAT_NO_DR', 'AC_STAT_NO_CR',
        'AC_STAT_BLOCK', 'AC_STAT_STOP_PAY', 'AC_STAT_DORMANT', 'AC_STAT_FROZEN', 'JOINT_AC_INDICATOR', 'AC_OPEN_DATE',
        'AC_STMT_DAY', 'AC_STMT_CYCLE', 'AC_STMT_TYPE', 'ALT_AC_NO', 'CHEQUE_BOOK_FACILITY', 'ATM_FACILITY',
        'PASSBOOK_FACILITY', 'DR_GL', 'CR_GL', 'ACY_OPENING_BAL', 'LCY_OPENING_BAL', 'ACY_TODAY_TOVER_DR',
        'ACY_TODAY_TOVER_CR', 'ACY_CURR_BALANCE', 'LCY_CURR_BALANCE', 'ACY_BLOCKED_AMOUNT', 'ACY_AVL_BAL',
        'ACY_MTD_TOVER_DR', 'ACY_MTD_TOVER_CR', 'DATE_LAST_CR_ACTIVITY', 'DATE_LAST_DR_ACTIVITY', 'DATE_LAST_CR',
        'DATE_LAST_DR', 'DORMANCY_DATE', 'DORMANCY_DAYS', 'TOD_LIMIT', 'ADDRESS1', 'ADDRESS2', 'ADDRESS3',
        'IBAN_AC_NO', 'ACC_STATUS', 'STATUS_SINCE', 'MIN_REQD_BAL', 'SALARY_ACCOUNT', 'COUNTRY_CODE',
        'MODE_OF_OPERATION', 'AC_SET_CLOSE', 'AC_SET_CLOSE_DATE', 'IBAN_REQUIRED', 'DIRECT_BANKING'] + list(AUD) +
        ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    bw = TableWriter(out, 'STTM_ACCOUNT_BALANCE', ['CUST_AC_BRN', 'CUST_AC_NO', 'ACY_WITHDRAWABLE_BAL', 'ACY_UNCOLLECTED',
                                                    'ACY_BLOCKED_AMT', 'AC_STAT_DORMANT', 'CCY', 'ACY_UNAUTH_CR'])
    dw = TableWriter(out, 'STTM_CUST_ACCOUNT_DORMANCY', ['BRANCH_CODE', 'CUST_AC_NO', 'DORMANCY_START_DT',
                                                          'DORMANCY_END_DT', 'REF_NO'])
    hw = TableWriter(out, 'ACTB_ACCBAL_HISTORY', ['BRANCH_CODE', 'ACCOUNT', 'BKG_DATE', 'ACY_OPENING_BAL',
                                                   'LCY_OPENING_BAL', 'ACY_CLOSING_BAL', 'LCY_CLOSING_BAL',
                                                   'ACY_DR_TUR', 'LCY_DR_TUR', 'ACY_CR_TUR', 'LCY_CR_TUR', 'ACC_CCY',
                                                   'ACY_CLOSING_AVLBAL', 'ACY_CLOSING_UNCOLL', 'ACY_CLOSING_BLOCK'])
    by_acct = collections.defaultdict(list)
    for (no, d), (dr, cr) in E.daymov.items():
        by_acct[no].append((d, dr, cr))
    dseq = 0
    for a in ACCTS.values():
        rate = CCY_RATE[a.ccy]
        run = a.opening
        for d, dr, cr in sorted(by_acct.get(a.no, [])):
            if d > HIST_END:
                continue
            close = money(run - dr + cr, 3)
            hw.write([a.branch, a.no, d, money(run), money(run * rate), money(close), money(close * rate), money(dr),
                      money(dr * rate), money(cr), money(cr * rate), a.ccy, money(close), 0, 0])
            run = close
        a.open_today = run
        dormant_now = a.dormant and not a.reactivated
        if a.dormant:
            dseq += 1
            dw.write([a.branch, a.no, a.dorm_since, a.reactivated, f'DORM{dseq:08d}'])
        c = a.cust
        closed = a.closed is not None
        aw.write(dict(
            BRANCH_CODE=a.branch, CUST_AC_NO=a.no, AC_DESC=f'{c.name} {CLASS[a.cls][1]}'[:105], CUST_NO=c.no, CCY=a.ccy,
            ACCOUNT_CLASS=a.cls, AC_STAT_NO_DR='Y' if closed else 'N', AC_STAT_NO_CR='Y' if closed else 'N',
            AC_STAT_BLOCK='N', AC_STAT_STOP_PAY='N', AC_STAT_DORMANT='Y' if dormant_now else 'N', AC_STAT_FROZEN='N',
            JOINT_AC_INDICATOR='S', AC_OPEN_DATE=a.open, AC_STMT_DAY=31, AC_STMT_CYCLE='M', AC_STMT_TYPE='D',
            ALT_AC_NO=a.no, CHEQUE_BOOK_FACILITY='Y' if a.kind == 'C' else 'N',
            ATM_FACILITY='Y' if any(cd['acct'] is a for cd in c.cards) else 'N', PASSBOOK_FACILITY='N',
            DR_GL=CLASS[a.cls][3], CR_GL=CLASS[a.cls][3], ACY_OPENING_BAL=money(a.open_today),
            LCY_OPENING_BAL=money(a.open_today * rate), ACY_TODAY_TOVER_DR=money(a.today_dr),
            ACY_TODAY_TOVER_CR=money(a.today_cr), ACY_CURR_BALANCE=money(a.bal), LCY_CURR_BALANCE=money(a.bal * rate),
            ACY_BLOCKED_AMOUNT=0, ACY_AVL_BAL=money(a.bal + a.od), ACY_MTD_TOVER_DR=money(a.mtd_dr),
            ACY_MTD_TOVER_CR=money(a.mtd_cr), DATE_LAST_CR_ACTIVITY=a.last_cr, DATE_LAST_DR_ACTIVITY=a.last_dr,
            DATE_LAST_CR=a.last_cr, DATE_LAST_DR=a.last_dr, DORMANCY_DATE=a.dorm_since if dormant_now else None,
            DORMANCY_DAYS=(TODAY - a.dorm_since).days if dormant_now else None, TOD_LIMIT=a.od or None,
            ADDRESS1=c.name[:105], ADDRESS2=c.area, ADDRESS3=c.emirate, IBAN_AC_NO=a.iban,
            ACC_STATUS='NORM', STATUS_SINCE=a.open, MIN_REQD_BAL=CLASS[a.cls][5],
            SALARY_ACCOUNT='Y' if a.salary else 'N', COUNTRY_CODE='AE', MODE_OF_OPERATION='S',
            AC_SET_CLOSE='Y' if closed else 'N', AC_SET_CLOSE_DATE=a.closed,
            IBAN_REQUIRED='Y', DIRECT_BANKING='Y', **dict(aud(a.open, f'OPS{a.branch}', f'CHK{a.branch}'),
                                                       RECORD_STAT='C' if closed else 'O')))
        bw.write([a.branch, a.no, money(a.bal), 0, 0, 'Y' if dormant_now else 'N', a.ccy, 0])
    for w in (aw, bw, dw, hw):
        w.close()


def write_cards(out):
    w = TableWriter(out, 'STTM_DEBIT_CARD_MASTER', [
        'BRANCH_CODE', 'REQUEST_REFERENCE_NO', 'CARD_NO', 'CARD_SEQ_NO', 'CUST_NO', 'CUST_AC_NO', 'CARD_PRODUCT',
        'PRIMARY_CARD', 'NAME_ON_CARD', 'OWNER_ID_NO', 'CARD_APPL_DATE', 'CARD_ISSUED_DT', 'CARD_EXPIRY_DT',
        'ACTIVATION_DT', 'CARD_STATUS', 'LAST_STATUS_UPDATED', 'ATM_LIMIT_UNIT', 'ATM_AMOUNT_LIMIT', 'ATM_COUNT_LIMIT',
        'POS_LIMIT_UNIT', 'POS_AMOUNT_LIMIT', 'POS_COUNT_LIMIT', 'CARD_BIN', 'ISSUER', 'CARD_BLOCKED', 'CARD_TYPE'] +
        list(AUD) + ['MAKER_DT_STAMP', 'CHECKER_DT_STAMP'])
    for c in CUSTS:
        for cd in c.cards:
            fraud = 'CARD_FRAUD_CNP' in c.scen
            status = 'C' if cd['status'] == 'C' else ('B' if fraud else 'A')
            w.write(dict(BRANCH_CODE=cd['acct'].branch, REQUEST_REFERENCE_NO=cd['ref'], CARD_NO=cd['pan'],
                         CARD_SEQ_NO=cd['seq'], CUST_NO=c.no, CUST_AC_NO=cd['acct'].no, CARD_PRODUCT=cd['product'],
                         PRIMARY_CARD='Y', NAME_ON_CARD=c.name.upper()[:26], OWNER_ID_NO=c.eid,
                         CARD_APPL_DATE=cd['issued'] - dt.timedelta(days=5), CARD_ISSUED_DT=cd['issued'],
                         CARD_EXPIRY_DT=cd['exp'], ACTIVATION_DT=cd['issued'] + dt.timedelta(days=R.randint(1, 20)),
                         CARD_STATUS=status, LAST_STATUS_UPDATED=TODAY if status != 'A' else cd['issued'],
                         ATM_LIMIT_UNIT='D', ATM_AMOUNT_LIMIT=None, ATM_COUNT_LIMIT=None, POS_LIMIT_UNIT='D',
                         POS_AMOUNT_LIMIT=None, POS_COUNT_LIMIT=None, CARD_BIN='400000', ISSUER=BANK_CODE,
                         CARD_BLOCKED='Y' if status == 'B' else 'N', CARD_TYPE='DEBIT',
                         **aud(cd['issued'], f'OPS{c.branch}', f'CHK{c.branch}')))
    w.close()


def loan_status(dpd):
    return 'NORM' if dpd == 0 else 'PDO1' if dpd <= 30 else 'PDO2' if dpd <= 60 else 'PDO3' if dpd <= 90 else 'NPA'


def write_loans(out):
    mw = TableWriter(out, 'CLTB_ACCOUNT_APPS_MASTER', [
        'ACCOUNT_NUMBER', 'BRANCH_CODE', 'APPLICATION_NUM', 'CUSTOMER_ID', 'PRODUCT_CODE', 'PRODUCT_CATEGORY',
        'BOOK_DATE', 'VALUE_DATE', 'MATURITY_DATE', 'AMOUNT_FINANCED', 'DOWNPAYMENT_AMOUNT', 'CURRENCY',
        'ORIGINAL_ST_DATE', 'PRIMARY_APPLICANT_ID', 'PRIMARY_APPLICANT_NAME', 'USER_DEFINED_STATUS', 'ACCOUNT_STATUS',
        'AMOUNT_DISBURSED', 'NO_OF_INSTALLMENTS', 'FREQUENCY', 'FREQUENCY_UNIT', 'DR_PROD_AC', 'CR_PROD_AC',
        'EMI_AMOUNT', 'DELINQUENCY_STATUS', 'DERIVED_STATUS', 'AUTH_STAT', 'MAKER_ID', 'CHECKER_ID'])
    cw = TableWriter(out, 'CLTB_ACCOUNT_COMPONENTS', ['ACCOUNT_NUMBER', 'BRANCH_CODE', 'COMPONENT_NAME',
                                                       'SETTLEMENT_CCY', 'COMPONENT_TYPE', 'MAIN_COMPONENT',
                                                       'CAPITALIZED', 'LIQUIDATION_MODE'])
    sw = TableWriter(out, 'CLTB_ACCOUNT_SCHEDULES', [
        'ACCOUNT_NUMBER', 'BRANCH_CODE', 'COMPONENT_NAME', 'SCHEDULE_TYPE', 'SCHEDULE_ST_DATE', 'SCHEDULE_DUE_DATE',
        'GRACE_DAYS', 'ORIG_AMOUNT_DUE', 'AMOUNT_DUE', 'AMOUNT_SETTLED', 'AMOUNT_OVERDUE', 'SETTLEMENT_CCY',
        'LCY_EQUIVALENT', 'EMI_AMOUNT', 'SCHEDULE_FLAG', 'WAIVER_FLAG', 'EVENT_SEQ_NO', 'CAPITALIZED', 'SCH_STATUS',
        'ACCOUNT_GL', 'LAST_PMNT_VALUE_DATE', 'SCHEDULE_NO', 'AMOUNT_WAIVED'])
    pw = TableWriter(out, 'CLTB_AMOUNT_PAID', ['ACCOUNT_NUMBER', 'BRANCH_CODE', 'COMPONENT_NAME', 'DUE_DATE', 'PAID_DATE',
                                                'EVENT_SEQ_NO', 'AMOUNT_PAID', 'AMOUNT_WAIVED', 'AMOUNT_CAPITALIZED',
                                                'EXEC_DATE', 'PAID_STATUS', 'START_DATE'])
    uw = TableWriter(out, 'CLTB_ACCOUNT_UDE_VALUES', ['ACCOUNT_NUMBER', 'BRANCH_CODE', 'EFFECTIVE_DATE', 'UDE_ID',
                                                       'UDE_VALUE', 'MAINT_VALUE', 'RESOLVED_VALUE', 'CODE_USAGE'])
    xw = TableWriter(out, 'CLTB_ACCOUNT_CREDIT_SCORE', ['ACCOUNT_NUMBER', 'BRANCH_CODE', 'RULENAME', 'CREDIT_SCORE',
                                                         'AUTO_CR_SCORE', 'AGENCY_CODE', 'EXT_CR_SCORE'])
    gw = TableWriter(out, 'CLTB_ACC_GUARANTOR_CUSTOMER', ['BRANCH_CODE', 'ACCOUNT_NUMBER', 'SEQUENCE_NO',
                                                           'GUARANTOR_CIF', 'COMPONENT_NAME'])
    for L in LOANS:
        c, prod = L['cust'], L['prod']
        unpaid = [s for s in L['sched'] if s['due'] <= TODAY and not s['paid']]
        dpd = (TODAY - unpaid[0]['due']).days if unpaid else 0
        st = loan_status(dpd)
        closed = all(s['paid'] for s in L['sched'])
        mw.write(dict(ACCOUNT_NUMBER=L['no'], BRANCH_CODE=L['branch'], APPLICATION_NUM=f'APP{L["no"][-9:]}',
                      CUSTOMER_ID=c.no, PRODUCT_CODE=prod, PRODUCT_CATEGORY=LOAN[prod][2], BOOK_DATE=L['book'],
                      VALUE_DATE=L['book'], MATURITY_DATE=L['mat'], AMOUNT_FINANCED=L['amount'],
                      DOWNPAYMENT_AMOUNT=L['down'] or None, CURRENCY='AED', ORIGINAL_ST_DATE=L['book'],
                      PRIMARY_APPLICANT_ID=c.no, PRIMARY_APPLICANT_NAME=c.name[:105], USER_DEFINED_STATUS=st,
                      ACCOUNT_STATUS='L' if closed else 'A', AMOUNT_DISBURSED=L['amount'],
                      NO_OF_INSTALLMENTS=L['tenor'], FREQUENCY=1, FREQUENCY_UNIT='M', DR_PROD_AC=L['acct'].no,
                      CR_PROD_AC=L['acct'].no, EMI_AMOUNT=L['emi'], DELINQUENCY_STATUS='Y' if dpd else 'N',
                      DERIVED_STATUS=st, AUTH_STAT='A', MAKER_ID=f'LOS{L["branch"]}', CHECKER_ID=f'CRD{L["branch"]}'))
        for comp, typ, main in (('PRINCIPAL', 'L', 'N'), ('MAIN_INT', 'I', 'Y')):
            cw.write([L['no'], L['branch'], comp, 'AED', typ, main, 'N', 'A'])
        uw.write([L['no'], L['branch'], L['book'], 'INTEREST_RATE', L['rate'], L['rate'], L['rate'], 'P'])
        score = c.score if c.type == 'I' else 900 - c.score * 55
        xw.write([L['no'], L['branch'], 'RETAIL_SCORECARD' if c.type == 'I' else 'SME_SCORECARD',
                  int(min(100, max(1, (score - 300) / 6))), int(min(100, max(1, (score - 300) / 6 + R.randint(-5, 5)))),
                  'AEC', str(score)])
        if L['guarantor']:
            gw.write([L['branch'], L['no'], 1, L['guarantor'].no, 'PRINCIPAL'])
        for s in L['sched']:
            overdue = s['due'] <= TODAY and not s['paid']
            s_dpd = (TODAY - s['due']).days if overdue else 0
            for comp, amt, gl in (('PRINCIPAL', s['prin'], LOAN[prod][3]), ('MAIN_INT', s['int'], '310100001')):
                sw.write([L['no'], L['branch'], comp, 'P', s['start'], s['due'], 0, amt, amt,
                          amt if s['paid'] else 0, amt if overdue else 0, 'AED', amt, L['emi'], 'N', 'N', s['evt'],
                          'N', loan_status(s_dpd) if overdue else 'NORM', gl, s['paid'], s['no'], 0])
                if s['paid']:
                    pw.write([L['no'], L['branch'], comp, s['due'], s['paid'], s['evt'], amt, 0, 0, s['paid'], 'Y',
                              s['start']])
    for w in (mw, cw, sw, pw, uw, xw, gw):
        w.close()


def write_aml(out, E):
    w = TableWriter(out, 'CSTB_AML_DAILY_TOV', ['BRANCH_CODE', 'BOOK_DATE', 'CIF_GROUP_INDICATOR', 'CIF_GROUP_NO',
                                                 'PRODUCT_CAT', 'LIMIT_CCY', 'DR_COUNT', 'DR_AMOUNT', 'CR_COUNT',
                                                 'CR_AMOUNT'])
    for (br, d, cust, cat), (dc, da, cc, ca) in sorted(E.aml.items()):
        if d <= HIST_END:
            w.write([br, d, 'C', cust, cat, 'AED', dc, money(da), cc, money(ca)])
    w.close()


def write_labels(out):
    import csv, gzip, io, json
    with gzip.GzipFile(os.path.join(out, 'DEMO_SCENARIO_LABELS.csv.gz'), 'wb', mtime=0) as gz:
        f = io.TextIOWrapper(gz, encoding='utf-8', newline='')
        w = csv.DictWriter(f, ['CUSTOMER_NO', 'CUST_AC_NO', 'SCENARIO', 'START_DATE', 'END_DATE', 'NOTES'])
        w.writeheader()
        for l in LABELS:
            w.writerow({k: (v.strftime('%Y-%m-%d 00:00:00') if isinstance(v, dt.date) else v) for k, v in l.items()})
        f.close()
    MANIFEST['DEMO_SCENARIO_LABELS'] = len(LABELS)
    json.dump({'seed': SEED, 'history_from': WIN_START.isoformat(), 'history_to': HIST_END.isoformat(),
               'branch_date': TODAY.isoformat(), 'rows': MANIFEST}, open(os.path.join(out, 'manifest.json'), 'w'),
              indent=1)


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--customers', type=int, default=2000)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data'))
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    n_corp = int(args.customers * .15)
    build_corporates(n_corp)
    build_individuals(args.customers - n_corp)
    finalize_corporates()
    build_loans()
    assign_scenarios()
    for c in CUSTS:
        (plan_individual if c.type == 'I' else plan_corporate)(c)
    plan_scenarios()
    plan_loans()
    plan_tds()
    print(f'customers={len(CUSTS)} accounts={len(ACCTS)} loans={len(LOANS)} events={len(EVENTS)}')
    write_static(out)
    E = Engine(out)
    process(E)
    rows = {}
    for w in (E.hist, E.daily, E.ft, E.sw):
        rows[w.table] = w.close()
    write_customers(out)
    write_accounts(out, E)
    write_cards(out)
    write_loans(out)
    write_aml(out, E)
    write_labels(out)
    print('rows:', rows)
    print('txn counts:', dict(E.stats.most_common()))
    print('labels:', collections.Counter(l['SCENARIO'] for l in LABELS))


if __name__ == '__main__':
    main()
