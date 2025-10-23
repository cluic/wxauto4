from wxauto4 import uia
from wxauto4.param import (
    WxParam, 
    WxResponse,
)
from wxauto4.utils.win32 import (
    SetClipboardFiles,
    SetClipboardData,
    SetClipboardText
)
from wxauto4.ui.component import (
    Menu
)
from wxauto4.logger import wxlog
from .base import (
    BaseUISubWnd
)
from wxauto4.msgs.msg import parse_msg

import time
import os
import re

def truncate_string(s: str, n: int=8) -> str:
    s = s.replace('\n', '').strip()
    return s if len(s) <= n else s[:n] + '...'

USED_MSG_IDS = {}
LAST_MSG_COUNT = {}

class ChatBox(BaseUISubWnd):
    def __init__(self, control: uia.Control, parent):
        self.control: uia.Control = control
        self.root = parent
        self.parent = parent  # `wx` or `chat`
        self.init()

    def _lang(self, text: str):
        return text
    
    @property
    def id(self):
        if self.msgbox.Exists(0):
            return self.msgbox.runtimeid
        return None
    
    @property
    def used_msg_ids(self):
        if self.id in USED_MSG_IDS:
            return USED_MSG_IDS[self.id]
        else:
            USED_MSG_IDS[self.id] = tuple()
            return USED_MSG_IDS[self.id]
    
    @property
    def who(self):
        if hasattr(self, '_who'):
            return self._who
        self._who = self.editbox.Name
        return self._who
    
    def get_info(self):
        chat_info = {}
        chat_info_control = self.control.GetParentControl().GroupControl(ClassName="mmui::ChatInfoView")
        aid_head = 'top_content_h_view.top_spacing_v_view.top_left_info_v_view.big_title_line_h_view.'
        v_view = "top_content_h_view.top_spacing_v_view.top_left_info_v_view"
        aids = {
            'chatname': "current_chat_name_label",
            'chat_count': "current_chat_count_label",
            'company': "current_chat_openim_name",
            'comicon': "openim_icon"
        }
        chat_info['chat_type'] = 'friend'
        for aid in aids:
            control = chat_info_control.TextControl(
                AutomationId=aid_head+aids[aid]
            )
            if control.Exists(0):
                if aid == 'chatname':
                    chat_info['chat_name'] = control.Name
                    if (
                        'chat_remark' not in chat_info
                        and (cnc := chat_info_control.GroupControl(AutomationId=v_view).GroupControl().TextControl()).Exists(0)
                    ):
                        chat_info['chat_remark'] = chat_info['chat_name']
                        chat_info['chat_name'] = cnc.Name

                elif aid == 'chat_count':
                    chat_info['group_member_count'] = int(re.findall('\d+', control.Name)[0])
                    chat_info['chat_type'] = 'group'
                elif aid == 'company':
                    chat_info['chat_type'] = 'service'
            if chat_info_control.ButtonControl(Name="公众号主页").Exists(0):
                    chat_info['chat_type'] = 'official'
        return chat_info
        
    
    def _activate_editbox(self):
        if not self.editbox.HasKeyboardFocus:
            self.editbox.MiddleClick()

    def init(self):
        self.msgbox = self.control.GroupControl(ClassName="mmui::MessageView").ListControl()
        self.editbox = self.control.EditControl(ClassName="mmui::ChatInputField")
        self.sendbtn = self.control.ButtonControl(Name=self._lang('发送(S)'))
        self.tools = self.control.ToolBarControl()
        self._empty = False
        # self._now_chat_info = self.get_info()
        # self.id = self.msgbox.runtimeid
        if (cid := self.id) and cid not in USED_MSG_IDS:
            # print("init chatbox", cid)
            USED_MSG_IDS[self.id] = tuple((i.runtimeid for i in self.msgbox.GetChildren()))
            LAST_MSG_COUNT[self.id] = len(USED_MSG_IDS[self.id])
            if not USED_MSG_IDS[cid]:
                self._empty = True

    def clear_edit(self):
        self._show()
        self.editbox.Click()
        self.editbox.SendKeys('{Ctrl}a', waitTime=0)
        self.editbox.SendKeys('{DELETE}')


    def send_text(self, content:str):
        t0 = time.time()
        while True:
            if time.time() - t0 > 5:
                return WxResponse.failure(f"发送消息超时：{content}")
            SetClipboardText(content)
            self._activate_editbox()
            self.editbox.SendKeys('{Ctrl}v')
            self.sendbtn.Click()
            time.sleep(0.1)
            if self.sendbtn.GetLegacyIAccessiblePattern().State == 0x100001:
                return WxResponse.success()

    def send_msg(self, content: str, clear: bool=True, at=None):
        wxlog.debug(f"发送消息: {content}")
        if not content and not at:
            return WxResponse.failure(f"`content` and `at` can't be empty at the same time")
        
        if clear:
            self.clear_edit()
        if at:
            self.input_at(at)

        return self.send_text(content)
    
    # @uilock
    def send_file(self, file_path):
        wxlog.debug(f"发送文件: {file_path}")
        if isinstance(file_path, str):
            file_path = [file_path]
        file_path = [os.path.abspath(f) for f in file_path]
        
        self.clear_edit()

        SetClipboardFiles(file_path)
        self.editbox.SendKeys('{Ctrl}v')
        self.sendbtn.Click()
        if self.sendbtn.GetLegacyIAccessiblePattern().State == 0x100001:
            return WxResponse.success()

    def input_at(self, at_list):
        if isinstance(at_list, str):
            at_list = [at_list]
        self._activate_editbox()
        for friend in at_list:
            self.editbox.SendKeys('@'+friend.replace(' ', ''))
            atmenu = AtMenu(self)
            atmenu.select(friend)
        
    def get_msgs(self):
        if self.msgbox.Exists(0):
            return [
                parse_msg(msg_control, self) 
                for msg_control 
                in self.msgbox.GetChildren()
                if uia.IsElementInWindow(self.msgbox, msg_control)
                # if msg_control.ControlTypeName in ('ListItemControl', 'CheckBoxControl')
            ]
        return []
    
    def get_new_msgs(self):
        if not self.msgbox.Exists(0):
            return []
        msg_controls = self.msgbox.GetChildren()
        now_msg_ids = tuple((i.runtimeid for i in msg_controls))
        current_msg_count = len(now_msg_ids)
        
        if not now_msg_ids:  # 当前没有消息id
            wxlog.debug("聊天窗口无消息")
            return []
        
        # 确保used_msg_ids不为None
        current_used_ids = self.used_msg_ids or tuple()
        
        if self._empty and current_used_ids:
            self._empty = False
        
        # 获取上次记录的消息数量
        last_msg_count = LAST_MSG_COUNT.get(self.id, 0)
        
        # 如果没有历史消息id，初始化
        if not current_used_ids:
            if not self._empty:
                # 初始化时记录当前所有消息id和数量
                USED_MSG_IDS[self.id] = now_msg_ids[-100:]
                LAST_MSG_COUNT[self.id] = current_msg_count
                return []
        
        # 关键改进：基于消息数量变化的检测机制
        msg_count_increased = current_msg_count > last_msg_count
        
        if msg_count_increased:
            # 消息数量增加了，计算新消息数量
            new_msg_count = current_msg_count - last_msg_count
            
            # 取最后N条消息作为候选新消息
            candidate_new_ids = now_msg_ids[-new_msg_count:]
            
            # 验证这些ID确实是新的（排除可能的ID重用情况）
            used_msg_ids_set = set(current_used_ids)
            confirmed_new_ids = []
            
            for msg_id in candidate_new_ids:
                if msg_id not in used_msg_ids_set:
                    confirmed_new_ids.append(msg_id)
                # 即使ID重复，如果消息数量确实增加了，也要包含这条消息
                # 这是处理快速重复消息的关键逻辑
                elif msg_count_increased and len(confirmed_new_ids) < new_msg_count:
                    # 对于疑似重复ID的情况，仍然当作新消息处理
                    confirmed_new_ids.append(msg_id)
            
            if confirmed_new_ids:
                # 更新记录
                USED_MSG_IDS[self.id] = now_msg_ids[-100:]
                LAST_MSG_COUNT[self.id] = current_msg_count
                
                # 根据新消息id获取对应的控件
                new_controls = [i for i in msg_controls if i.runtimeid in confirmed_new_ids]
                
                return [
                        parse_msg(msg_control, self) 
                        for msg_control 
                        in new_controls
                        if msg_control.ControlTypeName == 'ListItemControl'
                    ]
        
        # 如果消息数量没有增加，但可能有ID变化（处理消息刷新的情况）
        used_msg_ids_set = set(current_used_ids)
        new_ids = [msg_id for msg_id in now_msg_ids if msg_id not in used_msg_ids_set]
        
        if new_ids:
            # 更新记录
            USED_MSG_IDS[self.id] = now_msg_ids[-100:]
            LAST_MSG_COUNT[self.id] = current_msg_count
            
            # 根据新消息id获取对应的控件
            new_controls = [i for i in msg_controls if i.runtimeid in new_ids]
            
            return [
                    parse_msg(msg_control, self) 
                    for msg_control 
                    in new_controls
                    if msg_control.ControlTypeName == 'ListItemControl'
                ]
        
        return []


class AtEle:
    def __init__(self, control):
        self.name = control.Name
        self.control = control

class AtMenu(BaseUISubWnd):
    _ui_cls_name: str = "mmui::XPopover"
    _ui_name: str = "Weixin"
    _ui_automation_id = "MentionPopover"

    def __init__(self, parent):
        self.root = parent.root
        self.control = self.root.control.WindowControl(
            ClassName=self._ui_cls_name,
            Name=self._ui_name,
            AutomationId=self._ui_automation_id
        )

    def clear(self, friend):
        if self.exists():
            self.control.SendKeys('{ESC}')
        for _ in range(len(friend)+1):
            self.root._chat_api.editbox.SendKeys('{BACK}')

    def select(self, friend): 
        friend_ = friend.replace(' ', '')
        if self.exists():
            ateles = self.control.ListControl().GetChildren()
            if len(ateles) == 1:
                ateles[0].Click()
                return WxResponse.success()
            
            else:
                atele = self.control.ListItemControl(Name=friend)
                if atele.Exists(0):
                    uia.RollIntoView(self.control, atele)
                    atele.Click()
                    return WxResponse.success()
                else:
                    self.clear(friend_)
                    return WxResponse.failure('@对象不存在')
        else:
            self.clear(friend_)
            return WxResponse.failure('@选择窗口不存在')
        
    def list(self):
        return [AtEle(i) for i in self.control.ListControl().GetChildren()]