import functools
import json
import warnings
from contextlib import AbstractContextManager
from typing import List, Union, Tuple

import psycopg2


def if_empty_return_null(func):
    """
    if a keyerror is raised, cahnge the return to null

    :param func: the functions to wrap around
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IndexError:
            return None

    return wrapper


class Sandman_Sql(AbstractContextManager):
    def __init__(self, database_obj):
        self.database_obj = database_obj
        self._cursor = self.database_obj.cursor()
        self.in_use_cursor = self._cursor
        self.no_commit = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.no_commit:
            warnings.warn("exited without committing, is this intentional?")
        self._cursor.close()
        self.database_obj.close()

    @property
    def in_use_cursor(self):
        self.no_commit = False
        return self._cursor

    @in_use_cursor.setter
    def in_use_cursor(self, cursor):
        self.no_commit = True
        self._cursor = cursor

    def copycat_instance(self):
        """
        call this to get a different Sandman instance for a different cursor.
        :return: the copycat instance
        """
        return _Sandman_duplicate(self)

    def commit_all(self):
        if self.no_commit:
            warnings.warn("committing with nothing, is this intentional?")
        self.database_obj.commit()
        self.in_use_cursor.close()
        self.in_use_cursor = self.database_obj.cursor()

    def _database_add(self, table: str, members: List[str], values: List[str]):
        if not members or not values:
            raise ValueError("empty attributes list or attribute values")
        if len(members) != len(values):
            raise ValueError("inconsistent length between attributes and attribute values")
        try:
            marked_cursor = self.in_use_cursor
            # TODO: how to deal with number?
            members_str = ', '.join([i.upper() for i in members])
            values_str = ', '.join([f"'{i}'" for i in values])
            marked_cursor.execute(
                f"INSERT INTO {table.upper()} ({members_str})"
                f"VALUES({values_str});"
            )
            return True
        except Exception as e:
            raise ValueError("most likely duplicated primary key.\n" + str(e))

    def _database_delete(self, table: str, members: List[str], values: List[str]):
        if not members or not values:
            raise ValueError("empty attributes list or attribute values")
        if len(members) != len(values):
            raise ValueError("inconsistent length between attributes and attribute values")
        try:
            marked_cursor = self.in_use_cursor
            # TODO: how to deal with number?
            condition_str = ' AND '.join([f"{i}='{j}'" for i, j in zip(members, values)])
            marked_cursor.execute(
                f"DELETE FROM {table.upper()} WHERE {condition_str};"
            )
            return True
        except Exception as e:
            raise ValueError("most likely duplicated primary key.\n" + str(e))

    def _batch_get(self, table: str):
        try:
            # select method does not trigger the commit logging
            cursor = self._cursor
            cursor.execute(
                f"SELECT * FROM {table.upper()};")
            result = cursor.fetchall()
            return result

        except Exception as e:
            raise ValueError("some error happened\n" + str(e))

    def _database_get(self, table: str,
                      attributes_compared: List[str],
                      attr_val: List[str],
                      attr_wanted: List[str] = None):
        if not attributes_compared or not attr_val:
            raise ValueError("given lists are empty, one of them that is")

        if len(attributes_compared) != len(attr_val):
            raise ValueError("trying to get something from database that with inconsistent attribute lists")

        try:
            # select method does not trigger the commit logging
            cursor = self._cursor
            wanted_attr_str = ', '.join([i.upper() for i in attr_wanted]) if attr_wanted else '*'
            attr_comp_str = ' AND '.join([f"{i.upper()}='{j}'" for i, j in zip(attributes_compared, attr_val)])
            cursor.execute(
                f"SELECT {wanted_attr_str} FROM {table.upper()} "
                f"WHERE {attr_comp_str};")
            result = cursor.fetchall()
            return result

        except Exception as e:
            raise ValueError("some error happened\n" + str(e))

    def get_all_servers(self) -> List[Tuple[str, str]]:
        result = self._batch_get('SERVER')
        return [tuple(i) for i in result] if result else None

    def get_server(self, server_id: str) -> Union[Tuple[str, str], None]:
        result = self._database_get('SERVER',
                                    ['SERVERID'],
                                    [server_id])
        return tuple(result[0]) if result else None

    def get_admin_id(self, server_id: str):
        result = self._database_get('SERVER',
                                    ['SERVERID'],
                                    [server_id],
                                    attr_wanted=['ADMINROLEID'])
        return result[0][0] if result else None

    def get_menu_group(self, menu_group_name: str, server_id: str):
        result = self._database_get('MENU_GROUP',
                                    ['MENU_GROUP_NAME', 'SERVERID'],
                                    [menu_group_name, server_id])
        return tuple(result[0]) if result else None

    def get_menus_from_server(self, server_id: str):
        result = self._database_get('MENU',
                                    ['SERVERID'],
                                    [server_id])
        return [tuple(i) for i in result]

    def get_menus_from_group(self, group_name: str, server_id: str):
        result = self._database_get('MENU',
                                    ['MENU_GROUP_NAME', 'SERVERID'],
                                    [group_name, server_id])
        return [tuple(i) for i in result]

    @if_empty_return_null
    def get_menu(self, menu_msg_id: str):
        return self._database_get('MENU',
                                  ['MENUMSGID'],
                                  [menu_msg_id])[0]

    def get_menus(self):
        cursor = self._cursor
        cursor.execute("SELECT * FROM MENU;")
        result = cursor.fetchall()
        return [tuple(i) for i in result]

    def get_all_roles(self):
        cursor = self._cursor
        cursor.execute("SELECT * FROM CLASS_ROLE;")
        result = cursor.fetchall()
        return [tuple(i) for i in result]

    def get_all_relationships_from_menu_group(self, menu_msg_id: str):
        result = self._database_get('CLASS_IN_MENU',
                                    ['MENUMSGID'],
                                    [menu_msg_id])
        return result

    def get_relationships_from_menu_group(self, class_name: str, menu_msg_id: str):
        result = self._database_get('CLASS_IN_MENU',
                                    ['CLASS_NUMBER', 'MENUMSGID'],
                                    [class_name, menu_msg_id])
        return result

    @if_empty_return_null
    def get_class(self, class_name: str, school_name):
        return self._database_get('CLASS',
                                  ['CLASS_NUMBER', 'SCHOOL_NAME'],
                                  [class_name, school_name])[0]

    @if_empty_return_null
    def get_role_of_class(self, class_name, school_name):
        return self._database_get('CLASS_ROLE',
                                  ['CLASS_NUMBER', 'SCHOOL_NAME'],
                                  [class_name, school_name],
                                  attr_wanted=['ROLE_ID'])[0][0]

    def get_classes_from_menu_group(self, menu_name: str):
        cursor = self._cursor
        try:
            cursor.execute(f"SELECT class.CLASS_NUMBER,"
                           f"class.CLASS_FULL_NAME, "
                           f"class.SCHOOL_NAME, "
                           f"class.CLASS_DESCRIPTION "
                           f"FROM class JOIN class_in_menu_group cimg "
                           f"on class.class_number = cimg.class_number "
                           f"and class.school_name = cimg.school_name "
                           f"and cimg.menu_group_name='{menu_name}';")
            return cursor.fetchall()
        except Exception as e:
            raise ValueError("some error happened " + str(e))

    def get_classes_from_menu_id(self, menu_msg_id: str):
        """
        returns all the class attributes, with role_id at the end.
        """
        class_menu_relations = \
            self._database_get('CLASS_IN_MENU',
                               ['MENUMSGID'],
                               [menu_msg_id])
        classes = []
        for relation in class_menu_relations:
            cls = \
                self._database_get('CLASS',
                                   ['CLASS_NUMBER', 'SCHOOL_NAME'],
                                   [relation[0], relation[1]])
            classes.append([*cls[0], relation[2]])
        return classes

    @if_empty_return_null
    def get_star_msg(self, msg_id: str):
        return self._database_get('STAR_MESSAGE',
                                  ['MESGID'],
                                  [msg_id])[0]

    @if_empty_return_null
    def get_starboard(self, board_name: str, server_id: str):
        return self._database_get('STARBOARD',
                                  ['BOARD_NAME', 'SERVERID'],
                                  [board_name, server_id])[0]

    @if_empty_return_null
    def get_class_from_menu_group(self, menu_name: str, class_name: str):
        return self._database_get('CLASS_IN_MENU_GROUP',
                                  ['MENU_GROUP_NAME', 'CLASS_NUMBER'],
                                  [menu_name, class_name])[0]

    def add_server(self, server_id: str, owner_id: str, admin_role_id: str, mod_role_id: str):
        self._database_add('SERVER',
                           ['SERVERID', 'OWNERID', 'ADMINROLEID', 'MODROLEID'],
                           [server_id, owner_id, admin_role_id, mod_role_id])
        return True

    def add_starboard_msg(self, board: str, msg_id: str, server_id: str):
        self._database_add('STAR_MESSAGE',
                           ['MESGID', 'BOARD', 'SERVERID'],
                           [msg_id, board, server_id])
        return True

    def add_starboard(self, board_name, channel_id, server_id):
        self._database_add('STARBOARD',
                           ['BOARD_NAME', 'CHANNELID', 'SERVERID'],
                           [board_name, channel_id, server_id])
        return True

    def add_class(self,
                  class_name: str,
                  class_full_name: str,
                  school_name: str,
                  class_description: str,
                  server_id: str):
        self._database_add('CLASS',
                           ['CLASS_NUMBER', 'CLASS_FULL_NAME', 'SCHOOL_NAME', 'CLASS_DESCRIPTION', 'SERVERID'],
                           [class_name, class_full_name, school_name, class_description, server_id])
        return True

    def add_class_role(self, class_name: str, school_name: str, role_id: str):
        self._database_add('CLASS_ROLE',
                           ['CLASS_NUMBER', 'SCHOOL_NAME', 'ROLE_ID'],
                           [class_name, school_name, role_id])
        return True

    def add_ta_role(self, class_name: str, school_name: str, ta_role_id: str):
        self._database_add('CLASS_ROLE',
                           ['CLASS_NUMBER', 'SCHOOL_NAME', 'ROLE_ID', 'ROLE_TYPE'],
                           [class_name, school_name, ta_role_id, 'TA'])
        return True

    def add_class_to_menu_group(self, class_name: str, school_name: str, menu_name, server_id: str):
        self._database_add('CLASS_IN_MENU_GROUP',
                           ['CLASS_NUMBER', 'SCHOOL_NAME', 'MENU_GROUP_NAME', 'SERVERID'],
                           [class_name, school_name, menu_name, server_id])
        return True

    def add_class_to_menu(self, class_name: str, school_name: str, role_id: str, emoji_id: str, menu_msg_id: str):
        self._database_add('CLASS_IN_MENU',
                           ['CLASS_NUMBER', 'SCHOOL_NAME', 'ROLE_ID', 'EMOJIID', 'MENUMSGID'],
                           [class_name, school_name, role_id, emoji_id, menu_msg_id])
        return True

    def add_menu_group(self, group_name: str, server_id: str):
        self._database_add('MENU_GROUP',
                           ['MENU_GROUP_NAME', 'SERVERID'],
                           [group_name, server_id])
        return True

    def add_menu(self, menu_msg_id: str, channel_id: str, menu_name: str, server_id: str):
        if not self.get_menu_group(menu_name, server_id):
            raise ValueError(f'menu_group "{menu_name}" does not exist yet')
        self._database_add('MENU',
                           ['MENUMSGID', 'CHANNELID', 'MENU_GROUP_NAME', 'SERVERID'],
                           [menu_msg_id, channel_id, menu_name, server_id])
        return True

    def delete_menu_group(self, group_name: str, server_id: str):
        if not self.get_menu_group(group_name, server_id):
            return False
        self._database_delete('MENU_GROUP',
                              ['MENU_GROUP_NAME', 'SERVERID'],
                              [group_name, server_id])
        return True

    def delete_classes_in_menu(self, menu_msg_id: str):
        self._database_delete('CLASS_IN_MENU',
                              ['MENUMSGID'],
                              [menu_msg_id])
        return True

    def delete_menu(self, menu_msg_id: str, server_id: str):
        self._database_delete('MENU',
                              ['MENUMSGID', 'SERVERID'],
                              [menu_msg_id, server_id])

    def class_count_in_menu(self, menu_msg_id: str):
        if not self.get_menu(menu_msg_id):
            raise ValueError("the menu trying to count does not exist yet")
        return self._database_get('CLASS_IN_MENU',
                                  ['MENUMSGID'],
                                  [menu_msg_id],
                                  ["COUNT('CLASS_NUMBER')"])[0][0]


class _Sandman_duplicate(Sandman_Sql):
    """
    Creates a duplicate that can create new cursors.
    this cannot be context managed, as database is controlled in that one single instance.
    """

    def __init__(self, sandman: Sandman_Sql):
        super().__init__(sandman.database_obj)
        self.in_use_cursor = self.database_obj.cursor()

    def __enter__(self):
        raise AttributeError("cannot context manage, this is a duplicate instance."
                             "Only the main instance can close or enter.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise AttributeError("cannot context manage, this is a duplicate instance."
                             "Only the main instance can close or enter.")


def open_sandman_database():
    with open("server.json") as f:
        secret = json.loads(f.read())
    conn = psycopg2.connect(
        host=secret['host'],
        database="sandman",
        user="wzprichardwzp",
        password="Ac8c88767018698")
    return conn


def open_sandman_with_credential(database_name: str, user: str, password: str):
    conn = psycopg2.connect(
        host="sandman.postgres.database.azure.com",
        database=database_name,
        user=user,
        password=password)
    return conn


if __name__ == '__main__':
    # sand = Sandman_Sql(open_sandman_database())
    sand = Sandman_Sql(open_sandman_with_credential(
        'testing', 'wzprichardwzp', 'Ac8c88767018698'))
    # print(bool(sand.get_class_from_menu_group('Spring 2022', 'CY3740')))
    # print(sand.get_classes_from_menu_group('one'))
