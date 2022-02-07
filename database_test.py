import unittest
from postgres_database import Sandman_Sql, open_sandman_with_credential


class MyTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.database = Sandman_Sql(open_sandman_with_credential(
            'testing',
            'wzprichardwzp',
            'Ac8c88767018698'))
        self.server_id = '1234567'
        self.owner_id = 'richard'
        self.admin_id = 'admin'
        self.mod_id = 'mod'
        self.class_num = 1000

    def add_classes(self, amount: int, server_id: str, menu_name: str):
        self.database.add_menu_group(menu_name, self.server_id)
        for i in range(amount):
            self.database.add_class('CS' + str(self.class_num),
                                    'fundemental of ' + str(self.class_num),
                                    'NEU', '',
                                    server_id)
            self.class_num += 1
        self.database.commit_all()

    def database_setup(self):
        self.database.add_server(self.server_id,
                                 self.owner_id,
                                 self.admin_id,
                                 self.mod_id)
        self.database.commit_all()

    def database_tearDown(self) -> None:
        self.database._database_delete('SERVER',
                                       ['SERVERID'],
                                       [self.server_id])
        self.database.commit_all()

    def test_all_select(self):
        self.database_setup()

        if not self.database.get_server('1234567'):
            self.fail('database not exist')
        self.add_classes(5, self.server_id, 'test menu')
        count = self.database._database_get('CLASS_IN_MENU_GROUP',
                                    ['MENU_GROUP_NAME'],
                                    ['test menu'],
                                    attr_wanted=["COUNT('CLASS_NUMBER')"])[0]
        self.assertEqual(0, count[0])

        self.database_tearDown()

if __name__ == '__main__':
    unittest.main()
