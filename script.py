


from postgres_database import open_sandman_database, Sandman_Sql


if __name__ == '__main__':
    sand = Sandman_Sql(open_sandman_database())
    classes = sand._database_get('CLASS', ['SCHOOL_NAME'], ['NEU'])

    for cls in classes:
        sand.add_class_to_menu_group(cls[0], 'NEU', 'Spring 2022', '753022598392053770')

    sand.commit_all()