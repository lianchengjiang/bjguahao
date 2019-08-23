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
    def __init__(self):
        self.hospitalname = ''
        self.hospitalid = 0
        self.hospitalno = ''
        self.registerType = 0
        self.ishospitalcard = 0
        self.iscertificateid = 0
        self.Ismedicalcard = 0
        self.isresidentcard = 0
        self.address = ''
        self.levelName = ''
        self.image = ''
        self.areaName = ''


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

    def __init__(self, config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as yaml_file:
                data = yaml.load(yaml_file)
                debug_level = data["DebugLevel"]
                if debug_level == "debug":
                    self.debug_level = logging.DEBUG
                elif debug_level == "info":
                    self.debug_level = logging.INFO
                elif debug_level == "warning":
                    self.debug_level = logging.WARNING
                elif debug_level == "error":
                    self.debug_level = logging.ERROR
                elif debug_level == "critical":
                    self.debug_level = logging.CRITICAL

                logging.basicConfig(level=self.debug_level,
                                    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                                    datefmt='%a, %d %b %Y %H:%M:%S')

                self.mobile_no = data["username"]
                self.password = data["password"]
                self.date = data["date"]
                self.hospital_id = data["hospitalId"]
                self.department_id = data["departmentId"]
                self.duty_code = data["dutyCode"]
                self.patient_name = data["patientName"]
                self.hospital_card_id = data["hospitalCardId"]
                self.medicare_card_id = data["medicareCardId"]
                self.reimbursement_type = data["reimbursementType"]
                self.doctorName = data["doctorName"]
                self.children_name = data["childrenName"]
                self.children_idno = data["childrenIdNo"]
                self.cid_type = data["cidType"]
                self.children = data["children"]
                self.chooseBest = {"yes": True, "no": False}[data["chooseBest"]]
                self.patient_id = int()
                try:
                    self.useIMessage = data["useIMessage"]
                except KeyError:
                    self.useIMessage = "false"
                try:
                    self.useQPython3 = data["useQPython3"]
                except KeyError:
                    self.useQPython3 = "false"
                try:
                    self.children = data["children"]
                except KeyError:
                    self.children = "false"
                #
                logging.info("配置加载完成")
                logging.debug("手机号:" + str(self.mobile_no))
                logging.debug("挂号日期:" + str(self.date))
                logging.debug("医院id:" + str(self.hospital_id))
                logging.debug("科室id:" + str(self.department_id))
                logging.debug("上午/下午:" + str(self.duty_code))
                logging.debug("就诊人姓名:" + str(self.patient_name))
                logging.debug("所选医生:" + str(self.doctorName))
                logging.debug("是否挂儿童号:" + str(self.children))
                if self.children == "true":
                    logging.debug("患儿姓名:" + str(self.children_name))
                    logging.debug("患儿证件号" + str(self.children_idno))
                    logging.debug("患儿证件类型:" + str(self.cid_type))
                    logging.debug("患儿性别:" + str(GetInformation(self.children_idno).get_sex()))
                    logging.debug("患儿生日:" + str(GetInformation(self.children_idno).get_birthday()))
                logging.debug("使用mac电脑接收验证码:" + str(self.useIMessage))
                logging.debug("是否使用 QPython3 运行本脚本:" + str(self.useQPython3))

                if not self.date:
                    logging.error("请填写挂号时间")
                    exit(-1)

        except Exception as e:
            logging.error(repr(e))
            sys.exit()


class Guahao(object):
    """
    挂号
    """
    def __init__(self, config_path="config.yaml"):
        self.browser = Browser()
        self.dutys = ""
        self.refresh_time = ''

        self.login_url = "http://www.scgh114.com/web/login"
        self.send_code_url = "http://www.114yygh.com/v/sendorder.htm"
        self.get_doctor_url = "http://www.114yygh.com/dpt/partduty.htm"
        self.confirm_url = "http://www.114yygh.com/order/confirmV1.htm"
        self.patient_id_url = "http://www.114yygh.com/order/confirm/"
        self.department_url = "http://www.114yygh.com/dpt/appoint/"

        self.config = Config(config_path)  # config对象
        if self.config.useIMessage == 'true':
            # 按需导入 imessage.py
            import imessage
            self.imessage = imessage.IMessage()
        else:
            self.imessage = None

        if self.config.useQPython3 == 'true':
            try:  # Android QPython3 验证
                # 按需导入 qpython3.py
                import qpython3
                self.qpython3 = qpython3.QPython3()
            except ModuleNotFoundError:
                self.qpython3 = None
        else:
            self.qpython3 = None

    def get_cookie(self):
        cookie_url = "http://www.scgh114.com/"
        self.browser.get(cookie_url,data={})

    def update_hospital_list(self):
        hospital_list_url = "http://www.scgh114.com/web/hospital/findHospital"
        area_id = 10100  # 成都
        response = self.browser.post(hospital_list_url, data={'areaId': area_id})
        logging.info("更新医院列表完成：" + response.text)
        with open('hospital_list.json', 'w') as file:
            data = json.loads(response.text)
            json.dump(data, file, ensure_ascii=False, sort_keys=True, indent=4, separators=(',', ': '))

    def find_depart(self, hospital_id):
        url = "http://www.scgh114.com/web/hospital/findDepartByHosId"
        response = self.browser.post(url, data={'hospitalId': hospital_id})
        logging.info('departs:' + response.text)

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


    def registered(self):
        url = 'http://www.scgh114.com/web/register/registrationByType'
        params = {
            'workrecordid': 4923097,
            'hospitalno': 'SYY01',  #医院编号
            'hospitalname': '四川省人民医院', #医院名称
            'hospitaid': 88,  #医院id
            'isRealNameCard': 0, # 实名卡
            'iscertificateid': 0, # 身份证
            'workid': 791209, #
            'dutydate': '2019-08-23', #就诊日期
            'doctorid':	12617, #医生id
            'workDutyTimeNum': 	1, # 1表示上午，3表示下午
            'dutytime': '上午',
            'doctorName': '曾庆华',
            'type': 	1,
            'hospitalFlag': 	1,
            'username': '蒋连成',
            'certificateid': '450325199009171518',
            'tel': '18611471270',
            'txcode': self.verify_code(), #验证码
            'sex': 	1
        }
        response = self.browser.post(url, data=params)
        try:
            data = json.loads(response.text)
            if data["state"] == 0:
                # patch for qpython3
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

    def inputSth(self):

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
    # guahao.update_hospital_list()
    guahao.auth_login()
    guahao.registered()