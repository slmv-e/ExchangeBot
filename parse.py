import os
import requests
import pandas
from bs4 import BeautifulSoup
from get_tables import Authorization, auth_data_handler
from html import unescape


def lesson_handler() -> list:
    output_list = []

    # получение всех директорий
    with os.scandir("Output") as output_dir:
        lesson_list = sorted([lesson.name for lesson in output_dir if lesson.is_dir()])

    # вывод списка директорий
    print(" - Список домашних работ:")
    for i, lesson in enumerate(lesson_list):
        print(f'    {i + 1}. {lesson}')

    # выбор домашних работ
    selected_lessons = [lesson_list[index - 1] for index in map(int, input(
        " - Введите номер выбранного элемента, если нужно обработать "
        "несколько элементов, то введите их через пробел (например: 1 4 3): "
    ).split())]

    # выбор групп
    all_groups = bool(int(input(" - Выберите метод:\n"
                                "   1. Проверить определенные группы\n"
                                "   2. Проверить все группы\n"
                                " - Введите номер выбранного метода: ")) - 1)
    selected_groups = []

    if not all_groups:
        print(" - Введите номер группы (строго на английском), если групп несколько, "
              "то введите их через через Enter (чтобы завершить ввод, нажмите 2 раза Enter): ")
        while group := input():
            selected_groups.append(group)

        print(" - Список групп успешно пополнен")

    # обработка полученной информации
    for lesson_name in selected_lessons:
        lesson_table = pandas.read_excel(io=f"Output/{lesson_name}/Все_домашние_работы.xlsx")
        students_groups = list(lesson_table["№ группы"])
        students_links = list(lesson_table["Ссылка на работу"])

        selected_homeworks = [
            {
                'lesson_name': lesson_name,
                'group': student_group,
                'link': student_link
            }
            for student_group, student_link in zip(students_groups, students_links) if all_groups or student_group in selected_groups
        ]

        output_list.extend(selected_homeworks)

    return output_list


def parse(headers: dict, cookies_list: list, data: list):
    session = requests.Session()

    # добавляем cookie-файлы
    session.headers = headers
    for cookies in cookies_list:
        session.cookies.set(**cookies)

    # проходимся по каждому ученику из выбранной группы и домашки
    for data_slice in data:
        response = session.get(data_slice['link'] + '?status=checked').text
        soup = BeautifulSoup(response, 'html.parser')

        print(f" - Идет обработка домашней работы... \n"
              f"     Ссылка на работу: {data_slice['link']}")

        # список с информацией для post запросов
        post_request_list = [
            {
                'input_id': button.attrs['id'].split('_')[-1],
                'select': {
                    'id': select_html.attrs['id'].split('_')[-1],
                    'value': select_html.find('option', selected=True).text
                },
                'textarea': {
                    'id': textarea.attrs['id'].split('_')[-1],
                    'value': unescape(textarea.text)
                }
            }
            for button, select_html, textarea in zip(soup.find_all('input', class_='custom-control-input'),
                                                     soup.find_all('select', class_='form-control'),
                                                     soup.find_all('textarea',
                                                                   class_='form-control comment-form-children'))
        ]

        # данные для post запроса с принятием домашней работы
        apply_link = f"https://api.100points.ru/student_homework/apply/{data_slice['link'].split('/')[-1]}"
        apply_data = {}

        # проходимся по каждому заданию на странице
        for i, post_request in enumerate(post_request_list):
            post_link = f"https://api.100points.ru/student_homework/save_answer/{data_slice['link'].split('/')[-1]}"

            save_data = {
                f"is_validate:{post_request['input_id']}": 'on',
                f"points:{post_request['select']['id']}": post_request['select']['value'],
                f"comment:{post_request['textarea']['id']}": post_request['textarea']['value']
            }

            for key, value in save_data.items():
                apply_data[key] = value

            session.post(post_link, data=save_data)
            print(f"    - Задание №{i + 1} успешно обработано")

        session.post(apply_link, data=apply_data)
        print(" - Работа успешно обработана\n")


def main():
    login, password = auth_data_handler(key='parse')  # получаем логин и пароль
    data = lesson_handler()  # получаем список работ

    auth = Authorization(login, password)  # получаем cookie файлы
    auth.auth_cookies()

    parse(auth.headers, auth.cookies, data)  # начинаем работу


if __name__ == "__main__":
    main()
