#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
北京市预约挂号统一平台
"""

import os
import sys
import re
import json
import time
import datetime
import logging
from lib.prettytable import PrettyTable
import base64
import pytesseract
from PIL import Image
from PIL import ImageEnhance

class Hospital(object):
    hospitalname = ''
    hospitalid = 0
    hospitalno = ''
    registerType = 0
    ishospitalcard = 0
    iscertificateid = 0
    Ismedicalcard = 0
    isresidentcard = 0
    address = ''
    levelName = ''
    image = ''
    areaName = ''
    def __init__(self, dict):
        self.__dict__ = dict

    def description(self):
        return self.hospitalname


class Depart(object):
    deptname = ''
    deptno = ''
    deptid = 0
    def __init__(self, dict):
        self.__dict__ = dict

    def description(self):
        return self.deptname


class Doctor(object):
    doctorId = 0
    deptId = 0
    doctorSpecialityName = ''
    deptName = ''
    hospitalNo = ''
    doctorCode = ''
    hospitalId = 0
    degree = ''
    doctorName = ''
    image = ''
    hospitalName = ''
    extexperts = ''
    iscertificateid = -1
    ismedicalcard = -1
    isresidentcard = -1
    isRealNameCard = -1
    registerType = -1
    def __init__(self, dict):
        self.__dict__ = dict

    def merge(self, dict):
        self.__dict__ = {**self.__dict__, **dict}

    def description(self):
        return self.degree + ' ' + self.doctorName

class WorkInfo(object):
    workRecordId = 0
    workId = ''
    months = 0
    dutytime = 0
    count = 0
    price = ''
    state = 0
    scheduleTypeName = ''
    dutydate = ''
    dutytimestring = ''
    def __init__(self, dict):
        self.__dict__ = dict

    def description(self):
        time = '上午'
        if self.dutytime == 3:
            time = '下午'
        return self.dutydate + time

    @classmethod
    def formart_workinfo_list(cls, list):
        info_list = []
        for dict in list:
            for work_dict in dict['selWorks']:
                work_info = WorkInfo(work_dict)
                work_info.dutydate = dict['dutydate']
                work_info.dutytimestring = '上午'
                if work_info.dutytime == 3:
                    work_info.dutytimestring = '下午'
                info_list.append(work_info)
        return info_list

class Work(object):
    dutydate = ''
    selWorks = []
    def __init__(self, dict):
        self.__dict__ = dict


class DoctorSchedule(object):
    selWork = []
    doctor = []
    msg = ''
    state = ''
    def __init__(self, dict):
        self.__dict__ = dict


if sys.version_info.major != 3:
    logging.error("请在python3环境下运行本程序")
    sys.exit(-1)

try:
    import requests
except ModuleNotFoundError as e:
    logging.error("请安装python3 requests")
    sys.exit(-1)

from browser import Browser
from idcard_information import GetInformation

try:
    import yaml
except ModuleNotFoundError as e:
    logging.error("请安装python3 yaml模块")
    sys.exit(-1)


class Config(object):
    __instance = None
    def __init__(self, config_name='/config.json'):
        config_path = os.getcwd() + config_name
        self.config_path = config_path
        if os.path.exists(config_path):
            with open(config_path, "r") as file:
                data = json.load(file)
                self.hospital = data.get('hospital')
                self.depart = data.get('depart')
                self.doctor = data.get('doctor')
                self.time = data.get('time')
                self.name = data.get('name')
                self.certificateid = data.get('certificateid')
                self.phone = data.get('phone')

    def save(self):
        with open(self.config_path, 'w') as file:
            json.dump(self.__dict__, file)

    @classmethod
    def instance(cls):
        if not cls.__instance:
            cls.__instance = Config()
        return cls.__instance

class Guahao(object):
    """
    挂号
    """
    def __init__(self, config_path="config.yaml"):
        self.browser = Browser()
        self.dutys = ""
        self.refresh_time = ''

        self.config = Config()


    def output_selection(self, outlist, cls):
        string = '请输入要选择的序号：\n'
        for index, item in enumerate(outlist):
            instance = item
            if isinstance(item, dict):
                instance = cls(item)
            string = '%s%d. %s\n'%(string, index, instance.description())
        return string

    def get_cookie(self):
        cookie_url = "http://www.scgh114.com/"
        self.browser.get(cookie_url,data={})

    # 默认成都
    def input_hospital(self, area_id=10100):
        hospital_list_url = "http://www.scgh114.com/web/hospital/findHospital"
        response = self.browser.post(hospital_list_url, data={'areaId': area_id})

        hospital_list = json.loads(response.text)
        input_str = input(self.output_selection(hospital_list, Hospital))
        dict = {}
        if input_str:
            dict = hospital_list[int(input_str)]
            self.config.hospital = dict
        else:
            dict = self.config.hospital
        hospital = Hospital(dict)
        logging.info(hospital)
        self.input_depart(hospital.hospitalid)

    # 默认华西
    def input_depart(self, hospital_id=15):
        url = "http://www.scgh114.com/web/hospital/findDepartByHosId"
        response = self.browser.post(url, data={'hospitalId': hospital_id})
        response_data = json.loads(response.text)
        list = response_data['responseData']['data']['data']['depart']
        input_str = input(self.output_selection(list, Depart))

        dict = {}
        if input_str:
            dict = list[int(input_str)]
            self.config.depart = dict
        else:
            dict = self.config.depart
        depart = Depart(dict)
        self.input_doctor(depart.deptid)

    def input_doctor(self,depart_id):
        url = 'http://www.scgh114.com/web/hospital/searchDoctor'
        form = {
            'deptId': depart_id,
            'pageIndex': 1,
            'pageSize': 10,
            'key': ''
        }
        response = self.browser.post(url, data=form)
        response_data = json.loads(response.text)
        list = response_data[0]['data']
        input_str = input(self.output_selection(list, Doctor))
        dict = {}
        if input_str:
            dict = list[int(input_str)]
            self.config.doctor = dict
        else:
            dict = self.config.doctor
        doctor = Doctor(dict)
        self.input_time(doctor)

    def input_time(self, doctor:Doctor):
        url = 'http://www.scgh114.com/web/hospital/findDoctorWorkInfoById'
        form = {
            'doctorId': doctor.doctorId,
        }
        response = self.browser.post(url, data=form)
        response_data = json.loads(response.text)
        list = response_data['data']['selWork']
        format_list = WorkInfo.formart_workinfo_list(list)
        input_str = input(self.output_selection(format_list, Doctor))
        dict = {}
        if input_str:
            dict = format_list[int(input_str)].__dict__
            self.config.time = dict
        else:
            dict = self.config.time

        time = WorkInfo(dict)

        doctor.merge(response_data['data']['doctor'][0])
        self.registered(time, doctor)

    def convert_image(slef, img, standard=127.5):
        '''
        【图片裁剪】
        '''
        width = img.size[0]  # 图片大小
        height = img.size[1]
        border = 1
        img = img.crop((border, border, width-border, height-border))

        '''
        【图片放大】
        图片太小无法识别
        '''
        scale = 10
        img = img.resize((scale * img.size[0], scale * img.size[1]))

        '''
        【灰度转换】
        '''
        image = img.convert('L')

        '''
        【二值化】
        根据阈值 standard , 将所有像素都置为 0(黑色) 或 255(白色), 便于接下来的分割
        '''
        pixels = image.load()
        for x in range(image.width):
            for y in range(image.height):
                if pixels[x, y] > standard:
                    pixels[x, y] = 255
                else:
                    pixels[x, y] = 0
        return image

    def verify_code(self):
        url = 'http://www.scgh114.com/weixin/drawImage/code'
        response = self.browser.post(url, data={})
        path = os.getcwd() + '/verify_code.png'
        with open(path, 'wb') as file:
            file.write(response.content)
        image = Image.open(path)
        # image.show()
        image = self.convert_image(image, 220)

        # image.show()
        code = pytesseract.image_to_string(image, lang='enm')
        code = code.replace(' ','')
        logging.info('验证码：' + code)
        if len(code) == 4:
            return code
        else:
            return self.verify_code()


    def registered(self, work:WorkInfo, doctor:Doctor):
        url = 'http://www.scgh114.com/web/register/registrationByType'
        name = input('姓名：')
        if not name:
            name = self.config.name
        else:
            self.config.name = name

        certificateid = input('身份证号：')
        if not certificateid:
            certificateid = self.config.certificateid
        else:
            self.config.certificateid = certificateid

        phone = input('手机号：')
        if not name:
            phone = self.config.phone
        else:
            self.config.phone = phone

        self.config.save()

        params = {
            'workrecordid': work.workRecordId,
            'hospitalno': doctor.hospitalNo,  #医院编号
            'hospitalname': doctor.hospitalName, #医院名称
            'hospitaid': doctor.hospitalId,  #医院id
            'isRealNameCard': doctor.isRealNameCard, # 实名卡
            'iscertificateid': doctor.iscertificateid, # 身份证
            'workid': work.workId, #
            'dutydate': work.dutydate, #就诊日期
            'doctorid':	doctor.doctorId, #医生id
            'workDutyTimeNum': 	work.dutytime, # 1表示上午，3表示下午
            'dutytime': work.dutytimestring,
            'doctorName': doctor.doctorName,
            'type': 	1,
            'hospitalFlag': 	1,
            'username': name,
            'certificateid': certificateid,
            'tel': phone,
            'txcode': self.verify_code(), #验证码
            'sex': 	int(certificateid[16:17])
        }
        response = self.browser.post(url, data=params)
        try:
            data = json.loads(response.text)
            if data["state"] == 0:
                return True
            elif data["msg"] == '':
                self.auth_login(False)
                return self.registered()
            else:
                logging.error(data["msg"])
                raise Exception()

        except Exception as e:
            logging.error(e)
            logging.error("登陆失败")
            sys.exit(-1)


    def auth_login(self, use_cookie=True):
        """
        登陆
        """
        if (use_cookie):
            try:
            # patch for qpython3
                cookies_file = os.path.join(os.path.dirname(sys.argv[0]), "." + self.config.mobile_no + ".cookies")
                self.browser.load_cookies(cookies_file)
                logging.info("cookies登录")
                return True
            except Exception as e:
               pass

        logging.info("cookies登录失败")
        logging.info("开始使用账号密码登陆")
        password = self.config.password
        mobile_no = self.config.mobile_no
        payload = {
            'operLogin': mobile_no.encode(),
            'operPassword': password.encode()
        }
        response = self.browser.post(self.login_url, data=payload)
        logging.info("response data:" + response.text)
        try:
            data = json.loads(response.text)
            if data["state"] == 0:
                # patch for qpython3
                cookies_file = os.path.join(os.path.dirname(sys.argv[0]), "." + self.config.mobile_no + ".cookies")
                self.browser.save_cookies(cookies_file)
                logging.info("登陆成功:"+data["msg"])
                return True
            else:
                logging.error(data["msg"])
                raise Exception()

        except Exception as e:
            logging.error(e)
            logging.error("登陆失败")
            sys.exit(-1)

class Person(object):
    def __init__(self, name, nickname, age=0):
        self.name = name
        self.age = age
        self.nickname = nickname


if __name__ == "__main__":
    if (len(sys.argv) == 3) and (sys.argv[1] == '-c') and (isinstance(sys.argv[2], str)):
        config_path = sys.argv[2]
        guahao = Guahao(config_path)
    else:
        guahao = Guahao()
    # guahao.run()
    # guahao.update_hospital_list()
    # guahao.auth_login()

    # guahao.find_depart(15)
    guahao.get_cookie()
    guahao.input_hospital()

    # guahao.auth_login()
    # guahao.registered()