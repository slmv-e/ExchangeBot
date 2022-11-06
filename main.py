import requests
import fake_useragent
import pandas
import json
from threading import Thread
from bs4 import BeautifulSoup
from random import randint


class Authorization:
    def __init__(self, login: str, password: str):
        self.login = login
        self.password = password
        self.session = requests.Session()
        self.cookies = {}
        self.headers = {}

    def auth_cookies(self):
        url = "https://api.100points.ru/login"
        user_agent = fake_useragent.UserAgent().random

        self.headers = {
            "user-agent": user_agent
        }

        data = {
            'email': self.login,
            'password': self.password
        }

        self.session.post(url, data=data, headers=self.headers)  # response

        self.cookies = [
            {
                'domain': key.domain,
                'name': key.name,
                'path': key.path,
                'value': key.value
            }
            for key in self.session.cookies
        ]


class ExcelHandler:
    def __init__(self):
        self.students_dict = {}
        self.students_table = pandas.read_excel(io=r"Журнал Эбонит 2023.xlsx", sheet_name="Списки", usecols=[0, 1, 4])

    def get_students_dict(self):
        students_names = list(self.students_table["ФИО"])
        students_groups = list(self.students_table["№ группы"])
        students_emails = list(self.students_table["Unnamed: 4"])

        self.students_dict = dict([
            (students_emails[i], {
                'name': students_names[i],
                'group': students_groups[i]
            })
            for i in range(len(students_names))
        ])


def auth_data_handler() -> tuple:
    with open("Misc/config.json") as json_file:
        data = json.load(json_file)

    auth_info = data["authorization_data"]

    if auth_info["login"] != "" and auth_info["password"] != "" and \
            int(input("Вы уже авторизованы, если хотите сбросить данные, нажмите 1, иначе 0: ")) == 1 \
            or auth_info["login"] == "" or auth_info["password"] == "":  # если пользователь хочешь сбросить данные или данных нет
        login = str(input("Введите логин: "))
        password = str(input("Введите пароль: "))

        while int(input("Если данные введены верно нажмите 1, иначе 0: ")) == 0:
            login = str(input("Введите логин: "))
            password = str(input("Введите пароль: "))

        auth_info["login"], auth_info["password"] = login, password
        data["authorization_data"] = auth_info

        with open("Misc/config.json", 'w') as json_file:  # запись новых данных в файл
            json.dump(data, json_file, indent=4)
    return auth_info["login"], auth_info["password"]


def multiprocessing_preload(login: str, password: str) -> tuple:
    auth_app, excel_handler_app = Authorization(login=login, password=password), ExcelHandler()

    auth_process = Thread(target=auth_app.auth_cookies)
    excel_handler_process = Thread(target=excel_handler_app.get_students_dict)

    auth_process.start()
    excel_handler_process.start()

    auth_process.join()
    excel_handler_process.join()

    return auth_app.cookies, auth_app.headers, excel_handler_app.students_dict


def parse(cookies_list: list, headers: dict, students_dict: dict) -> tuple:
    output = {
        "№ группы": [],
        "ФИО ученика": [],
        "Почта": [],
        "Ссылка на работу": []
    }

    error_mail_output = {
        "ФИО ученика": [],
        "Почта": []
    }

    session = requests.Session()
    link = "https://api.100points.ru/exchange/index?status=is_controversial"

    # добавляем cookies
    for cookies in cookies_list:
        session.cookies.set(**cookies)

    response = session.get(link, headers=headers).text
    soup = BeautifulSoup(response, 'lxml')

    try:
        pages_cnt = int(soup.find_all('li', class_='paginate_button page-item')[-1].text.split()[0])
    except Exception as e:
        print("Что-то пошло не так...")
        print(e)
    else:
        index = 1
        for page in range(1, pages_cnt + 1):
            page_link = f"https://api.100points.ru/exchange/index?status=is_controversial&page={page}"
            page_response = session.get(page_link, headers=headers).text
            page_soup = BeautifulSoup(page_response, 'lxml')

            try:
                table_rows = page_soup.find('tbody').find_all('tr')
                for i in range(len(table_rows)):
                    student_info_block = table_rows[i].find_all('td')[2].find_all('div')
                    student_name, student_email = student_info_block[0].text, student_info_block[1].text
                    homework_link = table_rows[i].find_all('td')[0].find('a', href=True)['href']

                    try:
                        output["№ группы"].append(students_dict[student_email]["group"].lower())
                        output["ФИО ученика"].append(student_name)
                        output["Почта"].append(student_email)
                        output["Ссылка на работу"].append(homework_link)
                    except Exception as e:
                        if student_email not in error_mail_output["Почта"]:
                            error_mail_output["ФИО ученика"].append(student_name)
                            error_mail_output["Почта"].append(student_email)
                        print(f"{index + i}. Почта отсутствует в списке...", e)
                    else:
                        print(f'{index + i}. Домашняя работа ученика "{student_name}" успешна занесена')

            except Exception as e:
                print("Что-то пошло не так...")
                print(e)

            else:
                index += len(table_rows)

    return output, error_mail_output


def sort_output(raw_output: dict) -> dict:
    sorted_output = sorted(zip(raw_output["№ группы"],
                               raw_output["ФИО ученика"],
                               raw_output["Почта"],
                               raw_output["Ссылка на работу"]
                               ), key=lambda group_number: group_number[0])

    sorted_output_dict = {
        "№ группы": [],
        "ФИО ученика": [],
        "Почта": [],
        "Ссылка на работу": []
    }

    for item in sorted_output:
        sorted_output_dict["№ группы"].append(item[0])
        sorted_output_dict["ФИО ученика"].append(item[1])
        sorted_output_dict["Почта"].append(item[2])
        sorted_output_dict["Ссылка на работу"].append(item[3])

    return sorted_output_dict


def three_random_homeworks(input_dict: dict) -> dict:
    output_dict = {
        "№ группы": [],
        "ФИО ученика": [],
        "Почта": [],
        "Ссылка на работу": []
    }

    middle_dict = {
        key: []
        for key in list(set(input_dict['№ группы']))
    }

    count_of_works = 3

    for i in range(len(input_dict['№ группы'])):
        key = input_dict['№ группы'][i]
        name = input_dict['ФИО ученика'][i]
        link = input_dict['Ссылка на работу'][i]
        email = input_dict['Почта'][i]
        middle_dict[key].append((name, link, email))

    for key in middle_dict.keys():
        random_list = []

        while len(random_list) < count_of_works and len(random_list) < len(middle_dict[key]):
            if (random_number := randint(0, len(middle_dict[key]) - 1)) not in random_list:
                random_list.append(random_number)

        for item in random_list:
            output_dict['№ группы'].append(key)
            output_dict['ФИО ученика'].append(middle_dict[key][item][0])
            output_dict['Ссылка на работу'].append(middle_dict[key][item][1])
            output_dict['Почта'].append(middle_dict[key][item][2])

    return output_dict


def main():
    login, password = auth_data_handler()
    cookies_list, headers, students_dict = multiprocessing_preload(login=login, password=password)
    output_dict, error_mail_dict = parse(cookies_list=cookies_list, headers=headers, students_dict=students_dict)

    # экспорт данных в таблицу
    output_dataframe = pandas.DataFrame(sort_output(output_dict))
    error_mail_dataframe = pandas.DataFrame(error_mail_dict)
    three_random_homeworks_dataframe = pandas.DataFrame(sort_output(three_random_homeworks(output_dict)))

    output_dataframe.to_excel("Output/homeworks.xlsx")
    error_mail_dataframe.to_excel("Output/error_mail.xlsx")
    three_random_homeworks_dataframe.to_excel("Output/three_random_homeworks.xlsx")


if __name__ == "__main__":
    main()
