from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import urllib
import socket
import subprocess
from urllib import request
import logging
import os

host = ('', 807)
global oldIP
oldIP = ""


class Resquest(BaseHTTPRequestHandler):
    def do_GET(self):
        if '?' in self.path:
            # 解析参数
            queryString = urllib.parse.unquote(self.path.split('?', 1)[1])
            params = urllib.parse.parse_qs(queryString)
            userObj = params.get("user")
            psdObj = params.get("psd")
            vpsidObj = params.get("vpsid")
            if userObj is not None and psdObj is not None and vpsidObj is not None:

                user = userObj[0]
                psd = psdObj[0]
                vpsid = vpsidObj[0]

                self.send_response(204)  # 不返回结果
                self.send_header('Content-type', 'application/json')
                self.end_headers()

                disconres = False  # 断开ADSL结果
                while not disconres:
                    # 断开ADSL
                    disconres = disconnect()
                    time.sleep(1)

                dialresult = False  # 拨号结果
                while not dialresult:
                    # 链接ADSL
                    dialresult = connect(user, psd, vpsid)

                # 运行squid
                start_squid()

            else:
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'result': '参数异常'}).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'result': '请求异常'}).encode())


def int_log():
    # 将日志同时输出到文件和屏幕
    logger = logging.getLogger('')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(message)s')

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    fileHandler = logging.FileHandler(filename='C:\py.log', encoding='utf-8')
    fileHandler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(fileHandler)
    return


def disconnect():
    '''
    断开ADSL
    :return:
    '''
    name = "adsl"
    #cmdstr = "rasdial %s /DISCONNECT" % name
    cmdstr = "rasdial /DISCONNECT"
    # res = os.system(cmdstr)
    res = subprocess.call(cmdstr)
    if res == 0:
        logging.info("断开ADSL成功")
        return True
    else:
        logging.info("断开ADSL失败")
        return False


def connect(user, psd, vpsid):
    '''
    连接ADSL
    :param user:
    :param psd:
    :param vpsid:
    :return:
    '''
    name = "adsl"
    cmd_str = "rasdial %s %s %s" % (name, user, psd)
    # res = os.system(cmd_str)
    res = subprocess.call(cmd_str)
    if res == 0:
        time.sleep(0.5)
        global oldIP
        newIP = get_host_ip2()
        logging.info('拨号成功,IP地址为:%s,上个IP:%s' % (newIP, oldIP))
        if newIP == oldIP:
            oldIP = newIP
            logging.info("拨号IP与上个IP一样再次拨号")
            time.sleep(5)
            return False

        oldIP = newIP

        # IP入库
        time.sleep(3)
        inpNum = 0
        inputRes = False
        while inpNum < 10:
            inpNum += 1
            r = get("http://www.caimimao.cn/vpsinfo/updateVpsip.action?vpsid=%s&ip=%s" % (vpsid, newIP))
            if r is not None:
                obj = json.loads(r)
                if obj['success']:
                    logging.info("IP入库成功")
                    inputRes = True
                    return inputRes
                else:
                    logging.info("入库请求成功，录入失败,2秒后再次请求入库")
                    time.sleep(2)
            else:
                logging.info("IP入库失败,2秒后再次请求入库")
                time.sleep(2)
        if not inputRes:
            logging.info("10次入库失败，重新拨号")
            return False
    else:
        logging.info('拨号失败')
        logging.info(res)
        time.sleep(5)
        return False


def get(url):
    try:
        req = request.Request(url)
        read = request.urlopen(req).read()
        return read.decode('utf-8')
    except Exception as e:
        return


def get_host_ip():
    '''
    获取IP
    :return:
    '''
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip


def get_host_ip2():
    '''
    获取IP
    :return:
    '''
    logging.info("获取IP")
    num = 0
    while num < 2:
        addrs = socket.getaddrinfo(socket.gethostname(), None)
        logging.info("网卡数%s" % len(addrs))
        num = len(addrs)
        time.sleep(0.5)
    return addrs[len(addrs) - 1][4][0]


def start_squid():
    '''
    运行squid
    :return:
    '''
    if proc_exist("squid.exe"):
        subprocess.call('taskkill /F /IM squid.exe')
        logging.info("关闭squid")
        time.sleep(1)

    while not proc_exist("squid.exe"):
        subprocess.Popen('C:\squid\sbin\squid.exe', shell=True, close_fds=True)
        logging.info("运行squid...")
        time.sleep(1)


def proc_exist(proc_name):
    '''
    判断进程是否存在
    :param proc_name:
    :return:
    '''
    try:
        is_exist = False
        file_handle = os.popen('tasklist /FI "IMAGENAME eq ' + proc_name + '"')
        file_content = file_handle.read()
        if file_content.find(proc_name) > -1:
            is_exist = True
    except BaseException as e:
        logging.info(e)
    finally:
        return is_exist


if __name__ == '__main__':
    # 日志
    int_log()

    # 启动httpservice
    server = HTTPServer(host, Resquest)
    logging.info("Starting server, listen at: %s:%s" % host)
    server.serve_forever()
