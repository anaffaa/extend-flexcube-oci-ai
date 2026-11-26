"""Static reference data for the synthetic FLEXCUBE demo bank. All names are fictional."""

BANK_CODE = 'ODB1'
BANK_NAME = 'Oasis Demo Bank'
BANK_ID_IBAN = '099'          # fictional IBAN bank identifier
LCY = 'AED'

# code, name, emirate, area
BRANCHES = [
    ('000', 'Head Office', 'Dubai', 'Business Bay'),
    ('001', 'Deira Branch', 'Dubai', 'Deira'),
    ('002', 'Bur Dubai Branch', 'Dubai', 'Bur Dubai'),
    ('003', 'Dubai Marina Branch', 'Dubai', 'Dubai Marina'),
    ('004', 'Al Quoz Business Centre', 'Dubai', 'Al Quoz'),
    ('005', 'Abu Dhabi Main Branch', 'Abu Dhabi', 'Al Khalidiyah'),
    ('006', 'Mussafah Branch', 'Abu Dhabi', 'Mussafah'),
    ('007', 'Al Ain Branch', 'Al Ain', 'Al Jimi'),
    ('008', 'Sharjah Al Majaz Branch', 'Sharjah', 'Al Majaz'),
    ('009', 'Ajman Branch', 'Ajman', 'Al Nuaimiya'),
    ('010', 'Ras Al Khaimah Branch', 'Ras Al Khaimah', 'Al Nakheel'),
    ('011', 'Fujairah Branch', 'Fujairah', 'Fujairah City'),
]
EMIRATE_WEIGHTS = {'Dubai': .50, 'Abu Dhabi': .22, 'Sharjah': .13, 'Ajman': .05,
                   'Ras Al Khaimah': .04, 'Al Ain': .04, 'Fujairah': .02}
AREAS = {
    'Dubai': ['Al Barsha', 'Jumeirah Lake Towers', 'Al Nahda', 'Al Qusais', 'Deira', 'Karama',
              'International City', 'Discovery Gardens', 'Dubai Silicon Oasis', 'Mirdif', 'Business Bay',
              'Downtown Dubai', 'Dubai Marina', 'Al Warqa', 'Jumeirah', 'Arabian Ranches', 'Al Quoz'],
    'Abu Dhabi': ['Khalifa City', 'Al Reem Island', 'Mussafah', 'Al Khalidiyah', 'Al Mushrif',
                  'Mohammed Bin Zayed City', 'Al Raha', 'Tourist Club Area'],
    'Sharjah': ['Al Majaz', 'Al Nahda Sharjah', 'Al Taawun', 'Muwaileh', 'Al Khan'],
    'Ajman': ['Al Nuaimiya', 'Al Rashidiya', 'Al Jurf'],
    'Ras Al Khaimah': ['Al Nakheel', 'Al Hamra', 'Al Dhait'],
    'Al Ain': ['Al Jimi', 'Al Muwaiji', 'Al Towayya'],
    'Fujairah': ['Fujairah City', 'Dibba', 'Al Faseel'],
}

# iso2, name, region, blacklisted, iso numeric
COUNTRIES = [
    ('AE', 'UNITED ARAB EMIRATES', 'GCC', 'N', '784'), ('SA', 'SAUDI ARABIA', 'GCC', 'N', '682'),
    ('OM', 'OMAN', 'GCC', 'N', '512'), ('KW', 'KUWAIT', 'GCC', 'N', '414'), ('QA', 'QATAR', 'GCC', 'N', '634'),
    ('BH', 'BAHRAIN', 'GCC', 'N', '048'), ('IN', 'INDIA', 'ASI', 'N', '356'), ('PK', 'PAKISTAN', 'ASI', 'N', '586'),
    ('BD', 'BANGLADESH', 'ASI', 'N', '050'), ('LK', 'SRI LANKA', 'ASI', 'N', '144'), ('NP', 'NEPAL', 'ASI', 'N', '524'),
    ('PH', 'PHILIPPINES', 'ASI', 'N', '608'), ('CN', 'CHINA', 'ASI', 'N', '156'), ('EG', 'EGYPT', 'MEA', 'N', '818'),
    ('JO', 'JORDAN', 'MEA', 'N', '400'), ('LB', 'LEBANON', 'MEA', 'N', '422'), ('SY', 'SYRIA', 'MEA', 'N', '760'),
    ('NG', 'NIGERIA', 'AFR', 'N', '566'), ('ZA', 'SOUTH AFRICA', 'AFR', 'N', '710'), ('GB', 'UNITED KINGDOM', 'EUR', 'N', '826'),
    ('FR', 'FRANCE', 'EUR', 'N', '250'), ('DE', 'GERMANY', 'EUR', 'N', '276'), ('RU', 'RUSSIA', 'EUR', 'N', '643'),
    ('TR', 'TURKIYE', 'EUR', 'N', '792'), ('US', 'UNITED STATES', 'AME', 'N', '840'), ('TH', 'THAILAND', 'ASI', 'N', '764'),
    ('SG', 'SINGAPORE', 'ASI', 'N', '702'), ('HK', 'HONG KONG', 'ASI', 'N', '344'), ('EU', 'EUROPEAN UNION', 'EUR', 'N', '978'),
    ('IR', 'IRAN', 'MEA', 'Y', '364'), ('KP', 'NORTH KOREA', 'ASI', 'Y', '408'), ('MM', 'MYANMAR', 'ASI', 'Y', '104'),
]
HIGH_RISK_JURISDICTIONS = ['IR', 'KP', 'MM']        # blacklisted in the demo
ELEVATED_RISK_JURISDICTIONS = ['SY', 'NG', 'LB']    # used for enhanced due diligence in the demo

# code, name, country, decimals, iso numeric, rate to AED
CURRENCIES = [
    ('AED', 'UAE DIRHAM', 'AE', 2, '784', 1.0), ('USD', 'US DOLLAR', 'US', 2, '840', 3.6725),
    ('EUR', 'EURO', 'EU', 2, '978', 4.02), ('GBP', 'POUND STERLING', 'GB', 2, '826', 4.71),
    ('SAR', 'SAUDI RIYAL', 'SA', 2, '682', 0.979), ('OMR', 'OMANI RIAL', 'OM', 3, '512', 9.548),
    ('INR', 'INDIAN RUPEE', 'IN', 2, '356', 0.0428), ('PKR', 'PAKISTAN RUPEE', 'PK', 2, '586', 0.0131),
    ('PHP', 'PHILIPPINE PESO', 'PH', 2, '608', 0.0634), ('EGP', 'EGYPTIAN POUND', 'EG', 2, '818', 0.0755),
    ('BDT', 'BANGLADESH TAKA', 'BD', 2, '050', 0.0302),
]
CCY_RATE = {c[0]: c[5] for c in CURRENCIES}
CCY_NUM = {c[0]: c[4] for c in CURRENCIES}
HOME_CCY = {'IN': 'INR', 'PK': 'PKR', 'PH': 'PHP', 'EG': 'EGP', 'BD': 'BDT', 'GB': 'GBP', 'SA': 'SAR',
            'OM': 'OMR', 'US': 'USD', 'FR': 'EUR', 'DE': 'EUR', 'JO': 'USD', 'LB': 'USD', 'SY': 'USD',
            'LK': 'USD', 'NP': 'USD', 'RU': 'USD', 'CN': 'USD', 'ZA': 'USD', 'NG': 'USD', 'TR': 'EUR'}

CUSTOMER_CATEGORIES = [
    ('INDIVIDUAL', 'Retail individual'), ('PRIORITY', 'Priority banking individual'),
    ('STAFF', 'Bank staff'), ('SME', 'Small and medium enterprise'), ('CORPORATE', 'Corporate'),
]

# account class, description, class type (S/C/T), GL, dormancy days, min balance
ACCOUNT_CLASSES = [
    ('SAVIND', 'Savings Account Individual', 'S', '210100001', 365, 3000),
    ('CURIND', 'Current Account Individual', 'C', '210100002', 365, 3000),
    ('SALIND', 'Salary Account Individual', 'C', '210100002', 365, 0),
    ('PRISAV', 'Priority Savings Account', 'S', '210100001', 365, 100000),
    ('CURSME', 'SME Business Current Account', 'C', '210100003', 365, 10000),
    ('CURCOR', 'Corporate Current Account', 'C', '210100003', 365, 50000),
    ('USDCUR', 'USD Current Account', 'C', '210100003', 365, 1000),
    ('TDRETL', 'Fixed Deposit Retail', 'T', '210100004', 0, 10000),
    ('TDCORP', 'Fixed Deposit Corporate', 'T', '210100004', 0, 100000),
]

# trn code, description, module, product, product_cat, aml monitored, salary credit
TRN_CODES = [
    ('SAL', 'Salary Credit WPS', 'FT', 'FTIW', 'LOCALFT', 'N', 'Y'),
    ('PAY', 'Payroll Debit', 'FT', 'FTIN', 'LOCALFT', 'N', 'N'),
    ('ATM', 'ATM Cash Withdrawal', 'SW', 'ATMW', 'CASH', 'Y', 'N'),
    ('POS', 'Card Purchase POS', 'SW', 'POSP', 'CARD', 'N', 'N'),
    ('ECM', 'Card Purchase E-Commerce', 'SW', 'ECOM', 'CARD', 'N', 'N'),
    ('CSD', 'Cash Deposit Branch', 'RT', 'CDEP', 'CASH', 'Y', 'N'),
    ('CDM', 'Cash Deposit Machine', 'SW', 'CDMD', 'CASH', 'Y', 'N'),
    ('CSW', 'Cash Withdrawal Branch', 'RT', 'CWDL', 'CASH', 'Y', 'N'),
    ('FTI', 'Incoming Local Transfer', 'FT', 'FTIL', 'LOCALFT', 'N', 'N'),
    ('FTO', 'Outgoing Local Transfer', 'FT', 'FTOL', 'LOCALFT', 'N', 'N'),
    ('BKT', 'Book Transfer Internal', 'FT', 'FTIN', 'LOCALFT', 'N', 'N'),
    ('SWI', 'Incoming SWIFT Transfer', 'FT', 'FTIS', 'SWIFT', 'Y', 'N'),
    ('SWO', 'Outgoing SWIFT Transfer', 'FT', 'FTOS', 'SWIFT', 'Y', 'N'),
    ('BIL', 'Utility Bill Payment', 'PC', 'BILP', 'BILLS', 'N', 'N'),
    ('CHQ', 'Cheque Paid Clearing', 'CG', 'CHQP', 'CHEQUE', 'N', 'N'),
    ('CHD', 'Cheque Deposit Clearing', 'CG', 'CHQD', 'CHEQUE', 'N', 'N'),
    ('INT', 'Interest Credit', 'IC', 'ICCR', 'INTEREST', 'N', 'N'),
    ('CHG', 'Service Charges', 'IC', 'ICCH', 'CHARGES', 'N', 'N'),
    ('LND', 'Loan Disbursement', 'CL', None, 'LOAN', 'N', 'N'),
    ('LNR', 'Loan Repayment', 'CL', None, 'LOAN', 'N', 'N'),
    ('TDF', 'Term Deposit Funding', 'IC', 'TDBK', 'DEPOSIT', 'N', 'N'),
    ('TDM', 'Term Deposit Maturity Payout', 'IC', 'TDMT', 'DEPOSIT', 'N', 'N'),
]
TRN = {t[0]: t for t in TRN_CODES}

# gl code, description, parent, category (1 asset 2 liab 3 income 4 expense), type (1 nostro 5 cash 6 normal), customer flag
GLS = [
    ('100000000', 'ASSETS', '0', '1', '6', 'I'), ('200000000', 'LIABILITIES', '0', '2', '6', 'I'),
    ('300000000', 'INCOME', '0', '3', '6', 'I'), ('400000000', 'EXPENSES', '0', '4', '6', 'I'),
    ('110100001', 'Cash in Vault Branches', '100000000', '1', '5', 'I'),
    ('110200001', 'ATM and CDM Cash', '100000000', '1', '5', 'I'),
    ('120100001', 'Nostro Accounts Correspondent Banks', '100000000', '1', '1', 'I'),
    ('130100001', 'Central Bank Clearing UAEFTS and WPS', '100000000', '1', '6', 'I'),
    ('130200001', 'Cheque Clearing Account', '100000000', '1', '6', 'I'),
    ('140100001', 'Personal Loans', '100000000', '1', '6', 'C'),
    ('140100002', 'Auto Loans', '100000000', '1', '6', 'C'),
    ('140100003', 'Home Loans', '100000000', '1', '6', 'C'),
    ('140100004', 'SME Business Loans', '100000000', '1', '6', 'C'),
    ('190100001', 'Card Scheme Settlement Receivable', '100000000', '1', '6', 'I'),
    ('210100001', 'Savings Deposits', '200000000', '2', '6', 'C'),
    ('210100002', 'Current Deposits Individuals', '200000000', '2', '6', 'C'),
    ('210100003', 'Current Deposits Corporates', '200000000', '2', '6', 'C'),
    ('210100004', 'Fixed Deposits', '200000000', '2', '6', 'C'),
    ('290100001', 'Utility Billers Settlement', '200000000', '2', '6', 'I'),
    ('310100001', 'Interest Income Loans', '300000000', '3', '6', 'I'),
    ('320100001', 'Fee and Commission Income', '300000000', '3', '6', 'I'),
    ('410100001', 'Interest Expense Deposits', '400000000', '4', '6', 'I'),
    ('420100001', 'Staff Salaries', '400000000', '4', '6', 'I'),
]
GL = {g[0]: g for g in GLS}

# product, description, category, loan GL, rate range, tenor range (months)
LOAN_PRODUCTS = [
    ('PLN1', 'Personal Loan Salaried', 'PERSONAL', '140100001', (5.49, 9.49), (12, 48)),
    ('ALN1', 'Auto Loan New Vehicle', 'AUTO', '140100002', (3.49, 5.99), (24, 60)),
    ('HLN1', 'Home Loan Fixed Rate', 'MORTGAGE', '140100003', (3.99, 6.25), (120, 300)),
    ('SLN1', 'SME Business Term Loan', 'SME', '140100004', (7.00, 11.00), (24, 60)),
]
LOAN = {p[0]: p for p in LOAN_PRODUCTS}

# occupation, salary range AED per month, weight
OCCUPATIONS = [
    ('Labourer or Driver', (1800, 4500), .13), ('Retail or Hospitality Staff', (3000, 7500), .14),
    ('Administrative Staff', (6000, 14000), .15), ('Technician or Nurse', (7000, 16000), .12),
    ('Engineer or IT Professional', (15000, 38000), .14), ('Manager', (25000, 60000), .09),
    ('Senior Executive', (60000, 150000), .03), ('Government Employee', (20000, 65000), .07),
    ('Self-Employed', (15000, 120000), .06), ('Retired', (8000, 40000), .03), ('Homemaker or Student', (0, 0), .04),
]

NATIONALITY_WEIGHTS = {'AE': .14, 'IN': .25, 'PK': .10, 'EG': .07, 'PH': .08, 'GB': .05, 'JO': .04, 'LB': .03,
                       'BD': .04, 'SY': .03, 'US': .02, 'SA': .02, 'LK': .02, 'NP': .02, 'FR': .01, 'DE': .01,
                       'RU': .02, 'CN': .02, 'ZA': .01, 'NG': .01, 'TR': .01}
# share of salary typically remitted home (behaviour only, never used in risk scores)
REMIT_PROPENSITY = {'IN': .30, 'PK': .35, 'PH': .35, 'BD': .40, 'EG': .25, 'LK': .30, 'NP': .40, 'SY': .20,
                    'JO': .10, 'LB': .15, 'NG': .20, 'CN': .10, 'RU': .05}

FIRST = {
    'GULF_M': ['Mohammed', 'Ahmed', 'Khalid', 'Saeed', 'Rashid', 'Hamdan', 'Sultan', 'Abdulla', 'Omar', 'Hamad',
               'Majid', 'Faisal', 'Juma', 'Obaid', 'Saif', 'Humaid', 'Mansour', 'Nasser', 'Yousef', 'Ali'],
    'GULF_F': ['Fatima', 'Mariam', 'Aisha', 'Noura', 'Hessa', 'Shamma', 'Maitha', 'Alia', 'Latifa', 'Moza',
               'Reem', 'Amna', 'Sara', 'Hind', 'Khawla'],
    'IN_M': ['Rahul', 'Arjun', 'Vikram', 'Suresh', 'Ramesh', 'Anil', 'Rajesh', 'Pradeep', 'Sanjay', 'Manoj',
             'Abdul', 'Joseph', 'Thomas', 'Biju', 'Shaji', 'Sreejith', 'Naveen', 'Karthik', 'Harish', 'Vivek'],
    'IN_F': ['Priya', 'Anjali', 'Deepa', 'Lakshmi', 'Divya', 'Sneha', 'Meera', 'Kavya', 'Asha', 'Neha', 'Shalini', 'Reshma'],
    'PK_M': ['Muhammad', 'Imran', 'Asif', 'Bilal', 'Usman', 'Kamran', 'Zeeshan', 'Faisal', 'Tariq', 'Waqas', 'Adnan', 'Hamza'],
    'PK_F': ['Ayesha', 'Sana', 'Hina', 'Mahnoor', 'Fatima', 'Zainab', 'Nida', 'Rabia'],
    'EG_M': ['Mohamed', 'Ahmed', 'Mahmoud', 'Mostafa', 'Karim', 'Amr', 'Tamer', 'Hany', 'Sherif', 'Hossam'],
    'EG_F': ['Mona', 'Dina', 'Rania', 'Yasmin', 'Nermeen', 'Heba', 'Salma', 'Mai'],
    'LEV_M': ['Omar', 'Rami', 'Fadi', 'Samer', 'Tarek', 'Ziad', 'Nabil', 'Hani', 'Bassam', 'Wael'],
    'LEV_F': ['Lina', 'Rania', 'Dima', 'Hala', 'Nour', 'Rasha', 'Maya', 'Sawsan'],
    'PH_M': ['Jose', 'Mark', 'John Paul', 'Rommel', 'Jerome', 'Christian', 'Ramon', 'Joel'],
    'PH_F': ['Maria', 'Kristine', 'Joy', 'Rowena', 'Grace', 'Jennifer', 'Angelica', 'Mary Ann'],
    'BD_M': ['Mohammad', 'Rahim', 'Karim', 'Shafiq', 'Jahangir', 'Rafiq', 'Habib'], 'BD_F': ['Nasrin', 'Shirin', 'Fatema'],
    'SAS_M': ['Nimal', 'Kasun', 'Ruwan', 'Ram', 'Bikash', 'Suman'], 'SAS_F': ['Dilani', 'Sita', 'Anusha'],
    'WEST_M': ['James', 'Oliver', 'Thomas', 'Daniel', 'Matthew', 'Andrew', 'Richard', 'Simon', 'John', 'Michael', 'David'],
    'WEST_F': ['Emma', 'Sophie', 'Charlotte', 'Hannah', 'Laura', 'Rachel', 'Victoria', 'Sarah', 'Jessica'],
    'EU_M': ['Pierre', 'Lukas', 'Jonas', 'Antoine', 'Dmitry', 'Sergey', 'Mehmet', 'Emre'],
    'EU_F': ['Claire', 'Anna', 'Julia', 'Elena', 'Olga', 'Elif'],
    'CN_M': ['Wei', 'Jun', 'Hao', 'Lei'], 'CN_F': ['Li Na', 'Mei', 'Xin'],
    'AF_M': ['Thabo', 'Chinedu', 'Emeka', 'Sipho'], 'AF_F': ['Ngozi', 'Zanele', 'Amara'],
}
LAST = {
    'AE': ['Al Mansoori', 'Al Hammadi', 'Al Ketbi', 'Al Mazrouei', 'Al Shamsi', 'Al Dhaheri', 'Al Nuaimi', 'Al Suwaidi',
           'Al Falasi', 'Al Marri', 'Al Kaabi', 'Al Zaabi', 'Al Blooshi', 'Al Hosani', 'Al Mheiri', 'Al Romaithi'],
    'SA': ['Al Qahtani', 'Al Ghamdi', 'Al Otaibi', 'Al Harbi', 'Al Shehri', 'Al Zahrani'],
    'IN': ['Nair', 'Menon', 'Pillai', 'Sharma', 'Patel', 'Shah', 'Reddy', 'Iyer', 'Kumar', 'Singh', 'Varghese',
           'Mathew', 'Das', 'Gupta', 'Rao', 'Kurian', 'Khan', 'Shaikh'],
    'PK': ['Khan', 'Ahmed', 'Hussain', 'Malik', 'Qureshi', 'Butt', 'Chaudhry', 'Iqbal', 'Raza', 'Siddiqui', 'Mirza'],
    'EG': ['Abdelrahman', 'Hassan', 'Mostafa', 'El Sayed', 'Fahmy', 'Ibrahim', 'Soliman', 'Farouk', 'Gamal'],
    'LEV': ['Haddad', 'Khoury', 'Saleh', 'Nasser', 'Odeh', 'Barakat', 'Shami', 'Darwish', 'Khalil', 'Rizk', 'Aoun', 'Zein'],
    'PH': ['Santos', 'Reyes', 'Cruz', 'Bautista', 'Garcia', 'Mendoza', 'Dela Cruz', 'Ramos', 'Villanueva', 'Castillo'],
    'BD': ['Hossain', 'Rahman', 'Islam', 'Uddin', 'Miah', 'Chowdhury', 'Alam'],
    'SAS': ['Perera', 'Fernando', 'Silva', 'Gurung', 'Thapa', 'Shrestha'],
    'WEST': ['Smith', 'Jones', 'Taylor', 'Brown', 'Wilson', 'Evans', 'Walker', 'Hughes', 'Clarke', 'Wright', 'Miller', 'Davis'],
    'EU': ['Martin', 'Bernard', 'Schmidt', 'Weber', 'Ivanov', 'Petrov', 'Yilmaz', 'Demir'],
    'CN': ['Wang', 'Li', 'Zhang', 'Chen'], 'AF': ['Okafor', 'Nkosi', 'Adeyemi', 'Dlamini'],
}
NAME_GROUP = {'AE': ('GULF', 'AE'), 'SA': ('GULF', 'SA'), 'IN': ('IN', 'IN'), 'PK': ('PK', 'PK'), 'EG': ('EG', 'EG'),
              'JO': ('LEV', 'LEV'), 'LB': ('LEV', 'LEV'), 'SY': ('LEV', 'LEV'), 'PH': ('PH', 'PH'), 'BD': ('BD', 'BD'),
              'LK': ('SAS', 'SAS'), 'NP': ('SAS', 'SAS'), 'GB': ('WEST', 'WEST'), 'US': ('WEST', 'WEST'),
              'FR': ('EU', 'EU'), 'DE': ('EU', 'EU'), 'RU': ('EU', 'EU'), 'TR': ('EU', 'EU'), 'CN': ('CN', 'CN'),
              'ZA': ('AF', 'AF'), 'NG': ('AF', 'AF')}

CORP_PREFIX = ['Al Noor', 'Blue Coast', 'Desert Rose', 'Golden Sands', 'Gulf Bridge', 'Palm Crest', 'Falcon Ridge',
               'Oasis Point', 'Silver Dune', 'Pearl Bay', 'Crescent Line', 'Sea Breeze', 'Sandstone', 'Northstar',
               'Al Waha', 'Bright Horizon', 'Red Dune', 'Coral Reef', 'Green Palm', 'Al Safa', 'Emerald Gate',
               'Skyline Peak', 'Cedar Tree', 'Saffron', 'Mirage', 'Al Fanar', 'Dhow Harbour', 'Sapphire Stone']
# sector, description, risk (L/M/H), cash intensive, cross border
SECTORS = [
    ('General Trading', 'Import and re-export of general goods', 'H', False, True),
    ('Logistics', 'Freight forwarding and warehousing', 'M', False, True),
    ('Contracting', 'Building construction and fit-out', 'M', False, False),
    ('Technical Services', 'Electromechanical maintenance', 'L', False, False),
    ('Restaurant', 'Food and beverage outlets', 'M', True, False),
    ('Real Estate Brokers', 'Property brokerage and leasing', 'H', False, True),
    ('IT Solutions', 'Software and IT consulting', 'L', False, True),
    ('Auto Spare Parts', 'Vehicle spare parts trading', 'M', True, True),
    ('Jewellery', 'Gold and jewellery retail', 'H', True, True),
    ('Textiles', 'Garment and textile trading', 'M', True, True),
    ('Foodstuff Trading', 'Wholesale foodstuff distribution', 'L', True, False),
    ('Marine Services', 'Ship chandling and marine supplies', 'M', False, True),
    ('Facilities Management', 'Cleaning and facility services', 'L', False, False),
    ('Travel and Tourism', 'Travel agency and tour operator', 'M', True, True),
    ('Electronics Trading', 'Consumer electronics wholesale and re-export', 'H', True, True),
    ('Medical Supplies', 'Medical equipment distribution', 'L', False, True),
    ('Building Materials', 'Building materials trading', 'M', False, False),
]
LEGAL = ['LLC', 'LLC', 'LLC', 'FZE', 'FZCO', 'Est.']

# MCC, category, merchant name stems
MERCHANTS = {
    5411: ('Groceries', ['Fresh Basket Supermarket', 'Green Valley Hypermarket', 'Daily Needs Grocery', 'Al Madina Mini Mart']),
    5812: ('Restaurants', ['Spice Route Restaurant', 'Shawarma Corner', 'Harbour Grill', 'Bella Pasta', 'Karak House Cafe']),
    5814: ('Fast Food', ['Burger Lane', 'Quick Bites', 'Crispy Chicken Co']),
    5541: ('Fuel', ['Desert Fuel Station', 'Highway Petrol', 'City Fuel Point']),
    5912: ('Pharmacy', ['Life Care Pharmacy', 'Wellness Pharmacy', 'Al Shifa Pharmacy']),
    5732: ('Electronics', ['Gadget Hub', 'Tech World Electronics', 'Smart Choice Store']),
    5651: ('Clothing', ['Urban Threads', 'Style Avenue', 'Family Fashion Outlet']),
    5311: ('Department Store', ['City Centre Department Store', 'Mega Mall Store']),
    4121: ('Taxi and Ride Hailing', ['Metro Cab', 'RideNow App']),
    4511: ('Airlines', ['SkyLink Airways', 'Falcon Air', 'Gulf Wings']),
    7011: ('Hotels', ['Seaview Hotel', 'Desert Pearl Resort', 'City Inn Hotel']),
    4814: ('Telecom', ['Connect Mobile Recharge', 'NetLink Telecom']),
    5999: ('Online Marketplace', ['ShopSphere Online', 'MarketHub Online', 'QuickCart Online']),
    7832: ('Entertainment', ['Star Cinemas', 'Fun Zone']),
    8062: ('Hospitals', ['Al Noor Medical Centre', 'City Hospital']),
    8220: ('Education', ['Bright Minds School', 'Future Academy']),
}
UAE_CITIES = ['Dubai', 'Abu Dhabi', 'Sharjah', 'Ajman', 'Ras Al Khaimah', 'Al Ain', 'Fujairah']
FOREIGN_CITIES = [('GB', 'London', 'GBP'), ('FR', 'Paris', 'EUR'), ('TR', 'Istanbul', 'EUR'), ('TH', 'Bangkok', 'USD'),
                  ('IN', 'Mumbai', 'INR'), ('EG', 'Cairo', 'EGP'), ('US', 'New York', 'USD'), ('SG', 'Singapore', 'USD'),
                  ('SA', 'Riyadh', 'SAR'), ('OM', 'Muscat', 'OMR')]
CNP_FRAUD_ORIGINS = [('NG', 'Lagos'), ('RU', 'Moscow'), ('HK', 'Hong Kong'), ('US', 'Miami'), ('CN', 'Shenzhen')]
