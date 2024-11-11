# -*- coding: utf-8 -*-

import logging
import re
import time
import xml.etree.ElementTree as ET
from queue import Empty
from threading import Thread
from base.func_zhipu import ZhiPu

from wcferry import Wcf, WxMsg

from base.func_bard import BardAssistant
from base.func_chatglm import ChatGLM
from base.func_chatgpt import ChatGPT
from base.func_chengyu import cy
from base.func_news import News
from base.func_tigerbot import TigerBot
from base.func_xinghuo_web import XinghuoWeb
from configuration import Config
from constants import ChatType
from job_mgmt import Job

import requests
import json
import random

__version__ = "39.2.4.0"
__OverwatchWeChatRobotVersion__ = "0.3"


class Robot(Job):
    """个性化自己的机器人
    """

    def __init__(self, config: Config, wcf: Wcf, chat_type: int) -> None:
        self.wcf = wcf
        self.config = config
        self.LOG = logging.getLogger("Robot")
        self.wxid = self.wcf.get_self_wxid()
        self.allContacts = self.getAllContacts()

        if ChatType.is_in_chat_types(chat_type):
            if chat_type == ChatType.TIGER_BOT.value and TigerBot.value_check(self.config.TIGERBOT):
                self.chat = TigerBot(self.config.TIGERBOT)
            elif chat_type == ChatType.CHATGPT.value and ChatGPT.value_check(self.config.CHATGPT):
                self.chat = ChatGPT(self.config.CHATGPT)
            elif chat_type == ChatType.XINGHUO_WEB.value and XinghuoWeb.value_check(self.config.XINGHUO_WEB):
                self.chat = XinghuoWeb(self.config.XINGHUO_WEB)
            elif chat_type == ChatType.CHATGLM.value and ChatGLM.value_check(self.config.CHATGLM):
                self.chat = ChatGLM(self.config.CHATGLM)
            elif chat_type == ChatType.BardAssistant.value and BardAssistant.value_check(self.config.BardAssistant):
                self.chat = BardAssistant(self.config.BardAssistant)
            elif chat_type == ChatType.ZhiPu.value and ZhiPu.value_check(self.config.ZhiPu):
                self.chat = ZhiPu(self.config.ZhiPu)
            else:
                self.LOG.warning("未配置模型")
                self.chat = None
        else:
            if TigerBot.value_check(self.config.TIGERBOT):
                self.chat = TigerBot(self.config.TIGERBOT)
            elif ChatGPT.value_check(self.config.CHATGPT):
                self.chat = ChatGPT(self.config.CHATGPT)
            elif XinghuoWeb.value_check(self.config.XINGHUO_WEB):
                self.chat = XinghuoWeb(self.config.XINGHUO_WEB)
            elif ChatGLM.value_check(self.config.CHATGLM):
                self.chat = ChatGLM(self.config.CHATGLM)
            elif BardAssistant.value_check(self.config.BardAssistant):
                self.chat = BardAssistant(self.config.BardAssistant)
            elif ZhiPu.value_check(self.config.ZhiPu):
                self.chat = ZhiPu(self.config.ZhiPu)
            else:
                self.LOG.warning("未配置模型")
                self.chat = None

        self.LOG.info(f"已选择: {self.chat}")

    @staticmethod
    def value_check(args: dict) -> bool:
        if args:
            return all(value is not None for key, value in args.items() if key != 'proxy')
        return False

    def toAt(self, msg: WxMsg) -> bool:
        """处理被 @ 消息
        :param msg: 微信消息结构
        :return: 处理状态，`True` 成功，`False` 失败
        """
        pattern = r'^@Luna\s+/(.*)' 
        match = re.match(pattern, msg.content)
        if match:
            # @Luna /
            pattern_help = r'^help$'
            pattern_rank = r'^rank(.+)'
            pattern_info = r'^info(.+)'
            match_help = re.match(pattern_help, match.group(1))
            match_rank = re.match(pattern_rank, match.group(1))
            match_info = re.match(pattern_info, match.group(1))
            if match_help:
                # @Luna /help
                return self.toHelp(msg)

            elif match_rank:
                # @Luna /rank
                pt = r'^\s+(.+)'
                match_pt = re.match(pt, match_rank.group(1))
                if match_pt:
                    player_tag = match_pt.group(1).replace('#', '-')
                    print(f"/rank {player_tag}")
                    return self.get_player_rank(msg, player_tag)
                else:
                    return self.toWrongInstruction(msg)
                
            elif match_info:
                # @Luna /info
                pattern_q = r'^/q(.+)'
                pattern_c = r'^/c(.+)'
                match_q = re.match(pattern_q, match_info.group(1))
                match_c = re.match(pattern_c, match_info.group(1))
                if match_q:
                    # @Luna /info/q
                    pattern_type = r'^/(.+)\s+(.+)'
                    match_type = re.match(pattern_type, match_q.group(1))
                    if match_type:
                        # @Luna /info/q/{type} {tag}
                        player_tag = match_type.group(2).replace('#', '-')
                        print(f"/info/q/{match_type.group(1)} {player_tag}")
                        return self.get_player_quick_info(msg, player_tag = player_tag, type=match_type.group(1))
                    else:
                        pattern_type = r'^\s+(.+)'
                        match_type = re.match(pattern_type, match_q.group(1))
                        if match_type:
                            # @Luna /info/q {tag}
                            player_tag = match_type.group(1).replace('#', '-')
                            print(f"/info/q {player_tag}")
                            return self.get_player_quick_info(msg, player_tag = player_tag, type='time-played')
                        else:
                            return self.toWrongInstruction(msg)                   
                elif match_c:
                    # @Luna /info/c
                    return self.toWrongInstruction(msg)
                else:
                    return self.toWrongInstruction(msg)
            
            else:
                # 是/开头的指令但识别不了
                return self.toWrongInstruction(msg)
        
        else:
            # 不是 @Luna /开头的指令
            return self.toChitchat(msg)


    def toChengyu(self, msg: WxMsg) -> bool:
        """
        处理成语查询/接龙消息
        :param msg: 微信消息结构
        :return: 处理状态，`True` 成功，`False` 失败
        """
        status = False
        texts = re.findall(r"^([#|?|？])(.*)$", msg.content)
        # [('#', '天天向上')]
        if texts:
            flag = texts[0][0]
            text = texts[0][1]
            if flag == "#":  # 接龙
                if cy.isChengyu(text):
                    rsp = cy.getNext(text)
                    if rsp:
                        self.sendTextMsg(rsp, msg.roomid)
                        status = True
            elif flag in ["?", "？"]:  # 查词
                if cy.isChengyu(text):
                    rsp = cy.getMeaning(text)
                    if rsp:
                        self.sendTextMsg(rsp, msg.roomid)
                        status = True

        return status

    def toChitchat(self, msg: WxMsg) -> bool:
        """闲聊，接入 ChatGPT
        """
        # if not self.chat:  # 没接 ChatGPT，固定回复
        #     rsp = "你@我干嘛？"
        # else:  # 接了 ChatGPT，智能回复
        #     q = re.sub(r"@.*?[\u2005|\s]", "", msg.content).replace(" ", "")
        #     rsp = self.chat.get_answer(q, (msg.roomid if msg.from_group() else msg.sender))
        rsp = random.choice(["你@我干嘛？", "怎么了宝宝？", "未知的指令", "烦内", ])

        if rsp:
            if msg.from_group():
                self.sendTextMsg(rsp, msg.roomid, msg.sender)
            else:
                self.sendTextMsg(rsp, msg.sender)

            return True
        else:
            self.LOG.error(f"无法从 ChatGPT 获得答案")
            return False

    def toWrongInstruction(self, msg: WxMsg) -> bool:
        """处理错误指令
        """
        rsp = "未知或不完整的指令，使用“/help”查看帮助"
        if msg.from_group():
            self.sendTextMsg(rsp, msg.roomid, msg.sender)
        else:
            self.sendTextMsg(rsp, msg.sender)
        return True

    def toHelp(self, msg: WxMsg) -> bool:
        """处理帮助指令
        """
        rsp = f"""OverwatchWeChatRobot:{__OverwatchWeChatRobotVersion__}
查询公开生涯的PC端玩家信息
@机器人以使用指令
/rank {{player_tag}}  查询玩家PC预设职责段位
/info/q/{{type}} {{player_tag}}  查询玩家快速相关信息
/info/c/{{type}} {{player_tag}}  查询玩家竞技相关信息(未完成)
{{type}}可选内容包括：
time-played	角色游戏时间
games-won	角色胜利场数
weapon-accuracy	角色武器命中率
eliminations-per-life	角色击杀数 / 每条生命
critical-hit-accuracy	角色暴击率
multikill-best	角色最多单次消灭
objective-kills	角色目标点内击杀

Enjoy！
        """
        if msg.from_group():
            self.sendTextMsg(rsp, msg.roomid, msg.sender)
        else:
            self.sendTextMsg(rsp, msg.sender)
        return True

    def get_player_rank(self, msg: WxMsg, player_tag:str, api_key = 2211030):
        url = f"http://127.0.0.1:16524/v2/api/playerInfo?playerTag={player_tag}&apiKey={api_key}"
        
        try:
            response = requests.get(url)
            if response.status_code == 500:
                raise Exception("请求超时")
            if 'error' in response.text:  # 检查响应内容中是否包含'error'
                raise Exception(response.text + "\n请检查输入和生涯是否公开")
            
            response.raise_for_status()  # 这将抛出异常，如果响应的状态码不是 200
            
            # 解析 JSON 响应
            player_info = response.json()
            
            # 获取 playerCompetitivePC tcn
            player_competitive_info = player_info.get('playerCompetitiveInfo', {})
            pc_tank = player_competitive_info.get('PC', {}).get('Tank', {}).get('playerCompetitivePCTank')
            pc_tank_tier = player_competitive_info.get('PC', {}).get('Tank', {}).get('playerCompetitivePCTankTier')
            pc_damage = player_competitive_info.get('PC', {}).get('Damage', {}).get('playerCompetitivePCDamage')
            pc_damage_tier = player_competitive_info.get('PC', {}).get('Damage', {}).get('playerCompetitivePCDamageTier')
            pc_support = player_competitive_info.get('PC', {}).get('Support', {}).get('playerCompetitivePCSupport')
            pc_support_tier = player_competitive_info.get('PC', {}).get('Support', {}).get('playerCompetitivePCSupportTier')

            rank_list = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Grandmaster", "Champion"]
            def find_string_in_list(string, my_list):
                try:
                    return my_list.index(string)  # 查找字符串的索引
                except ValueError:
                    return -1  # 如果找不到，返回-1
                
            max_rank = max(find_string_in_list(pc_tank, rank_list), find_string_in_list(pc_damage, rank_list), find_string_in_list(pc_support, rank_list))
            
            result = f"查询到玩家 {player_info.get('playerBaseInfo', {}).get('playerTag', {})} 的信息：\n"
            result += f"Tank: {pc_tank} {pc_tank_tier}\n"
            result += f"Damage: {pc_damage} {pc_damage_tier}\n"
            result += f"Support: {pc_support} {pc_support_tier}\n"

            if max_rank == -1:
                pass
            elif max_rank == 0:
                result += "还得练。"
            elif max_rank == 1:
                result += "已经有Jaterchen的水平了。"
            elif max_rank == 2:
                result += "宗师指日可待。"
            elif max_rank == 3:
                result += random.choice(["别炸我白金兄弟！","为什么有人在白金狙击我！"])
            elif max_rank == 4:
                result += random.choice(["称霸钻石！","谁来了钻石都得老实。"])

            if result:
                if msg.from_group():
                    self.sendTextMsg(result, msg.roomid, msg.sender)
                else:
                    self.sendTextMsg(result, msg.sender)
                return True
            else:
                self.LOG.error(f"无法获得rank信息")
                return False
        
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}，请联系管理员")
            if msg.from_group():
                self.sendTextMsg(e, msg.roomid, msg.sender)
            return False
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}，请联系管理员")
            if msg.from_group():
                self.sendTextMsg(e, msg.roomid, msg.sender)
            return False
        except Exception as e:
            print(f"其他错误: {e}，请联系管理员")
            if msg.from_group():
                self.sendTextMsg(e, msg.roomid, msg.sender)
            return False
        
    def get_player_quick_info(self, msg: WxMsg, player_tag:str, type:str = "time-played", api_key = 2211030):
        """
            参数：{type}：必需，请求的排行榜类型，具体参数以解释如下

            type类型	解释说明
            time-played	角色游戏时间
            games-won	角色胜利场数
            weapon-accuracy	角色武器命中率
            eliminations-per-life	角色击杀数 / 每条生命
            critical-hit-accuracy	角色暴击率
            multikill-best	角色最多单次消灭
            objective-kills	角色目标点内击杀
        """
        url = f"http://127.0.0.1:16524/v2/api/playerPCQuickInfo?playerTag={player_tag}&apiKey={api_key}&type={type}"
        
        try:
            response = requests.get(url)
            if response.status_code == 500:
                raise Exception(response.text)
            elif 'error' in response.text:  # 检查响应内容中是否包含'error'
                raise Exception(response.text)
            
            response.raise_for_status()  # 这将抛出异常，如果响应的状态码不是 200
            
            # 解析 JSON 响应
            player_info = response.json()
            hero_rankings = player_info['heroRankings'][:10]
               
            result = f"查询到玩家 {player_info.get('playerTag', {})} 的快速比赛 {player_info.get('type', {})} 信息：\n"
            for r in hero_rankings:
                result += f"{r.get('heroName', {})}: {r.get('heroData', {})}\n"

            if result:
                if msg.from_group():
                    self.sendTextMsg(result, msg.roomid, msg.sender)
                else:
                    self.sendTextMsg(result, msg.sender)
                return True
            else:
                self.LOG.error(f"无法获得信息")
                return False
        
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}，请联系管理员")
            if msg.from_group():
                self.sendTextMsg(e, msg.roomid, msg.sender)
            return False
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}，请联系管理员")
            if msg.from_group():
                self.sendTextMsg(e, msg.roomid, msg.sender)
            return False
        except Exception as e:
            print(f"其他错误: {e}，请联系管理员")
            if msg.from_group():
                self.sendTextMsg(e, msg.roomid, msg.sender)
            return False


    def processMsg(self, msg: WxMsg) -> None:
        """当接收到消息的时候，会调用本方法。如果不实现本方法，则打印原始消息。
        此处可进行自定义发送的内容,如通过 msg.content 关键字自动获取当前天气信息，并发送到对应的群组@发送者
        群号：msg.roomid  微信ID：msg.sender  消息内容：msg.content
        content = "xx天气信息为："
        receivers = msg.roomid
        self.sendTextMsg(content, receivers, msg.sender)
        """

        # 群聊消息
        if msg.from_group():
            # 如果在群里被 @
            if msg.roomid not in self.config.GROUPS:  # 不在配置的响应的群列表里，忽略
                return

            if msg.is_at(self.wxid):  # 被@
                self.toAt(msg)

            else:  # 其他消息
                self.toChengyu(msg)

            return  # 处理完群聊信息，后面就不需要处理了

        # 非群聊信息，按消息类型进行处理
        if msg.type == 37:  # 好友请求
            self.autoAcceptFriendRequest(msg)

        elif msg.type == 10000:  # 系统信息
            self.sayHiToNewFriend(msg)

        elif msg.type == 0x01:  # 文本消息
            # 让配置加载更灵活，自己可以更新配置。也可以利用定时任务更新。
            if msg.from_self():
                if msg.content == "^更新$":
                    self.config.reload()
                    self.LOG.info("已更新")
            else:
                self.toChitchat(msg)  # 闲聊

    def onMsg(self, msg: WxMsg) -> int:
        try:
            self.LOG.info(msg)  # 打印信息
            self.processMsg(msg)
        except Exception as e:
            self.LOG.error(e)

        return 0

    def enableRecvMsg(self) -> None:
        self.wcf.enable_recv_msg(self.onMsg)

    def enableReceivingMsg(self) -> None:
        def innerProcessMsg(wcf: Wcf):
            while wcf.is_receiving_msg():
                try:
                    msg = wcf.get_msg()
                    self.LOG.info(msg)
                    self.processMsg(msg)
                except Empty:
                    continue  # Empty message
                except Exception as e:
                    self.LOG.error(f"Receiving message error: {e}")

        self.wcf.enable_receiving_msg()
        Thread(target=innerProcessMsg, name="GetMessage", args=(self.wcf,), daemon=True).start()

    def sendTextMsg(self, msg: str, receiver: str, at_list: str = "") -> None:
        """ 发送消息
        :param msg: 消息字符串
        :param receiver: 接收人wxid或者群id
        :param at_list: 要@的wxid, @所有人的wxid为：notify@all
        """
        # msg 中需要有 @ 名单中一样数量的 @
        ats = ""
        if at_list:
            if at_list == "notify@all":  # @所有人
                ats = " @所有人"
            else:
                wxids = at_list.split(",")
                for wxid in wxids:
                    # 根据 wxid 查找群昵称
                    ats += f" @{self.wcf.get_alias_in_chatroom(wxid, receiver)}"

        # {msg}{ats} 表示要发送的消息内容后面紧跟@，例如 北京天气情况为：xxx @张三
        if ats == "":
            self.LOG.info(f"To {receiver}: {msg}")
            self.wcf.send_text(f"{msg}", receiver, at_list)
        else:
            self.LOG.info(f"To {receiver}: {ats}\r{msg}")
            self.wcf.send_text(f"{ats}\n\n{msg}", receiver, at_list)

    def getAllContacts(self) -> dict:
        """
        获取联系人（包括好友、公众号、服务号、群成员……）
        格式: {"wxid": "NickName"}
        """
        contacts = self.wcf.query_sql("MicroMsg.db", "SELECT UserName, NickName FROM Contact;")
        return {contact["UserName"]: contact["NickName"] for contact in contacts}

    def keepRunningAndBlockProcess(self) -> None:
        """
        保持机器人运行，不让进程退出
        """
        while True:
            self.runPendingJobs()
            time.sleep(1)

    def autoAcceptFriendRequest(self, msg: WxMsg) -> None:
        try:
            xml = ET.fromstring(msg.content)
            v3 = xml.attrib["encryptusername"]
            v4 = xml.attrib["ticket"]
            scene = int(xml.attrib["scene"])
            self.wcf.accept_new_friend(v3, v4, scene)

        except Exception as e:
            self.LOG.error(f"同意好友出错：{e}")

    def sayHiToNewFriend(self, msg: WxMsg) -> None:
        nickName = re.findall(r"你已添加了(.*)，现在可以开始聊天了。", msg.content)
        if nickName:
            # 添加了好友，更新好友列表
            self.allContacts[msg.sender] = nickName[0]
            self.sendTextMsg(f"Hi {nickName[0]}，我自动通过了你的好友请求。", msg.sender)

    def newsReport(self) -> None:
        receivers = self.config.NEWS
        if not receivers:
            return

        news = News().get_important_news()
        for r in receivers:
            self.sendTextMsg(news, r)
