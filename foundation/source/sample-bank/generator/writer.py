"""CSV writer that validates every value against the FLEXCUBE column definitions."""
import csv, gzip, io, json, os, re, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
META = json.load(open(os.path.join(HERE, 'columns.json')))


def _limits(typ):
    m = re.match(r'(VARCHAR2|CHAR|NVARCHAR2|NCHAR)\((\d+)', typ)
    if m:
        return ('S', int(m.group(2)))
    m = re.match(r'NUMBER\((\d+)(?:,(\d+))?\)', typ)
    if m:
        return ('N', int(m.group(1)), int(m.group(2) or 0))
    if typ.startswith('NUMBER') or typ in ('FLOAT', 'INTEGER'):
        return ('N', None, None)
    if typ.startswith('DATE'):
        return ('D',)
    if typ.startswith('TIMESTAMP'):
        return ('T',)
    return ('X',)


class TableWriter:
    def __init__(self, out_dir, table, columns):
        types = dict(META[table]['columns'])
        unknown = [c for c in columns if c not in types]
        if unknown:
            raise ValueError(f'{table}: columns not in FLEXCUBE data model: {unknown}')
        self.table, self.columns = table, list(columns)
        self.lim = [_limits(types[c]) for c in self.columns]
        # every file carries all table columns in table order, so DBMS_CLOUD.COPY_DATA maps them by position
        self.all = [c for c, _ in META[table]['columns']]
        self.pos = [self.all.index(c) for c in self.columns]
        self.path = os.path.join(out_dir, f'{table}.csv.gz')
        self.fh = gzip.GzipFile(self.path, 'wb', mtime=0)
        self.txt = io.TextIOWrapper(self.fh, encoding='utf-8', newline='')
        self.w = csv.writer(self.txt)
        self.w.writerow(self.all)
        self.rows = 0

    def _fmt(self, i, v):
        if v is None or v == '':
            return ''
        lim, col = self.lim[i], self.columns[i]
        kind = lim[0]
        if kind == 'S':
            s = str(v)
            if len(s.encode('utf-8')) > lim[1]:
                raise ValueError(f'{self.table}.{col}: "{s}" longer than {lim[1]}')
            return s
        if kind == 'N':
            if isinstance(v, float):
                scale = lim[2] if lim[2] is not None else 3
                s = f'{round(v, scale):.{scale}f}'.rstrip('0').rstrip('.') if scale else str(int(round(v)))
            else:
                s = str(int(v))
            if lim[1] is not None:
                digits = len(s.lstrip('-').split('.')[0])
                if digits > lim[1] - lim[2]:
                    raise ValueError(f'{self.table}.{col}: {s} exceeds NUMBER({lim[1]},{lim[2]})')
            return s
        if kind == 'D':
            if isinstance(v, dt.datetime):
                return v.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(v, dt.date):
                return v.strftime('%Y-%m-%d 00:00:00')
            raise ValueError(f'{self.table}.{col}: not a date {v!r}')
        if kind == 'T':
            return v.strftime('%Y-%m-%d %H:%M:%S.%f')
        return str(v)

    def write(self, row):
        if isinstance(row, dict):
            extra = set(row) - set(self.columns)
            if extra:
                raise ValueError(f'{self.table}: unexpected keys {extra}')
            vals = [row.get(c) for c in self.columns]
        else:
            vals = row
            if len(vals) != len(self.columns):
                raise ValueError(f'{self.table}: {len(vals)} values for {len(self.columns)} columns')
        out = [''] * len(self.all)
        for i, v in enumerate(vals):
            out[self.pos[i]] = self._fmt(i, v)
        self.w.writerow(out)
        self.rows += 1

    def close(self):
        self.txt.close()
        MANIFEST[self.table] = self.rows
        return self.rows


MANIFEST = {}
