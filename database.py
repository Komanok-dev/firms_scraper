import sqlite3


class DatabaseHandler:
    def __init__(self, db_name='firms.db') -> None:
        self.db_name = db_name
        self.connection = None
        self.cursor = None
        self.tables = [
            '''CREATE TABLE IF NOT EXISTS Firm (
                id INTEGER PRIMARY KEY,
                name TEXT,
                headquater TEXT,
                logo TEXT
            );''',
            '''CREATE TABLE IF NOT EXISTS FirmOffice (
                id INTEGER PRIMARY KEY,
                name TEXT,
                city TEXT,
                slug TEXT,
                email TEXT,
                website TEXT,
                phone TEXT,
                address TEXT,
                firm_id INTEGER,
                FOREIGN KEY (firm_id) REFERENCES Firm(id)
            );''',
            '''CREATE TABLE IF NOT EXISTS Practice (
                id INTEGER PRIMARY KEY,
                name TEXT,
                tier TEXT,
                description TEXT,
                leading_individuals TEXT,
                practice_head TEXT,
                testimonials TEXT,
                key_clients TEXT,
                work_highlights TEXT
            );''',
            '''CREATE TABLE IF NOT EXISTS PracticeFirmOffice (
                practice_id INTEGER,
                firm_office_id INTEGER,
                PRIMARY KEY (practice_id, firm_office_id),
                FOREIGN KEY (practice_id) REFERENCES Practice(id),
                FOREIGN KEY (firm_office_id) REFERENCES FirmOffice(id)
            );''',
            '''CREATE TABLE IF NOT EXISTS Ranking (
                id INTEGER PRIMARY KEY,
                name TEXT
            );''',
            '''CREATE TABLE IF NOT EXISTS RankingFirmOffice (
                ranking_id INTEGER,
                firm_office_id INTEGER,
                PRIMARY KEY (ranking_id, firm_office_id),
                FOREIGN KEY (ranking_id) REFERENCES Ranking(id),
                FOREIGN KEY (firm_office_id) REFERENCES FirmOffice(id)
            );''',
            '''CREATE TABLE IF NOT EXISTS PracticeRanking (
                practice_id INTEGER,
                ranking_id INTEGER,
                PRIMARY KEY (practice_id, ranking_id),
                FOREIGN KEY (practice_id) REFERENCES Practice(id),
                FOREIGN KEY (ranking_id) REFERENCES Ranking(id)
            );'''
        ]

    def connect(self) -> None:
        self.connection = sqlite3.connect(self.db_name)
        self.cursor = self.connection.cursor()

    def create_tables(self) -> None:
        for table in self.tables:
            self.cursor.execute(table)
        self.connection.commit()

    def check_firm(self, firm: dict) -> None:
        '''Check if the firm with the same name already exists.'''
        self.cursor.execute('SELECT * FROM Firm WHERE name = ?', (firm['name'],))
        return True if self.cursor.fetchone() else False
    
    def check_office(self, office: dict) -> None:
        '''Check if an office with the same slug already exists.'''
        self.cursor.execute('SELECT * FROM FirmOffice WHERE slug = ?', (office['slug'],))
        return True if self.cursor.fetchone() else False

    def check_practice(self, practice: dict) -> None:
        '''Check if an practice with the same slug already exists.'''
        self.cursor.execute(
            'SELECT id FROM Practice WHERE name = ? AND tier = ? AND description = ?',
            (practice['name'], practice['tier'], practice['description'])
        )
        row = self.cursor.fetchone()
        return row[0] if row else False

    def check_ranking(self, ranking: str) -> None:
        '''Check if an practice with the same slug already exists.'''
        self.cursor.execute('SELECT id FROM Ranking WHERE name = ?', (ranking,))
        row = self.cursor.fetchone()
        return row[0] if row else False

    def insert_firm(self, firm: dict) -> None:
        '''Insert firm data into the database.'''
        # Insert firm data
        self.cursor.execute(
            'INSERT INTO Firm (name, headquater, logo) VALUES (?, ?, ?)',
            (firm['name'], firm['headquater'], firm['logo_url'])
        )
        firm_id = self.cursor.lastrowid

        # Insert office data
        for office in firm['office']:
            if self.check_office(office):
                continue
            query = '''
                INSERT INTO FirmOffice (
                    name, address, city, email, phone, slug, website, firm_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
            values = (
                office.get('name'), office.get('address'), office.get('city'),
                office.get('email'), office.get('phone'), office.get('slug'),
                office.get('website'), firm_id
            )
            self.cursor.execute(query, values)
            firm_office_id = self.cursor.lastrowid

            # Establish connections between office, practice, and ranking
            for practice in office.get('practice', []):
                # Insert practice data if it doesn't already exist
                practice_id = self.check_practice(practice)
                if not practice_id:
                    query = '''
                        INSERT INTO Practice (
                            name, tier, description, leading_individuals,
                            practice_head, testimonials, key_clients,
                            work_highlights
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                    values = (
                            practice['name'], practice['tier'], practice['description'],
                            practice['leading_individuals'], practice['practice_head'],
                            practice['testimonials'], practice['key_clients'],
                            practice['work_highlights']
                    )
                    self.cursor.execute(query, values)
                    practice_id = self.cursor.lastrowid

                # Connect office with practice
                self.cursor.execute(
                    'INSERT OR IGNORE INTO PracticeFirmOffice (practice_id, firm_office_id) VALUES (?, ?)',
                    (practice_id, firm_office_id)
                )

                # Establish connections between practice and ranking
                for ranking in office.get('ranking', []):
                    # Insert ranking data if it doesn't already exist
                    ranking_id = self.check_ranking(ranking)
                    if not ranking_id:
                        self.cursor.execute(
                            'INSERT INTO Ranking (name) VALUES (?)',
                            (ranking,)
                        )
                        ranking_id = self.cursor.lastrowid

                    # Connect practice with ranking
                    self.cursor.execute(
                        'INSERT OR IGNORE INTO PracticeRanking (practice_id, ranking_id) VALUES (?, ?)',
                        (practice_id, ranking_id)
                    )

                    # Connect office with ranking
                    self.cursor.execute(
                        'INSERT OR IGNORE INTO RankingFirmOffice (ranking_id, firm_office_id) VALUES (?, ?)',
                        (ranking_id, firm_office_id)
                    )

        self.connection.commit()

    def close_connection(self) -> None:
        if self.connection:
            self.connection.close()
