from .base import BaseUISubWnd, BaseUIWnd
from .navigationbox import NavigationBox
from .sessionbox import SessionBox
from .chatbox import ChatBox
from wxauto4.utils.win32 import (
    FindWindow,
    GetAllWindows,
    GetPathByHwnd,
    get_windows_by_pid,
    get_monitor_info
)
from wxauto4.param import WxParam, WxResponse, PROJECT_NAME
from wxauto4.logger import wxlog
from wxauto4 import uia
from typing import (
    Union, 
    List,
    Literal
)
import random
import os
import re
import sys

class WeChatSubWnd(BaseUISubWnd):
    _ui_cls_name: str = 'mmui::FramelessMainWindow'
    _win_cls_name: str = 'Qt51514QWindowIcon'
    _chat_api: ChatBox = None
    nickname: str = ''

    def __init__(
            self, 
            key: Union[str, int], 
            parent: 'WeChatMainWnd', 
            timeout: int = 3,
            resize:bool = False
        ):
        self.root = self
        self.parent = parent
        if isinstance(key, str):
            hwnd = FindWindow(classname=self._win_cls_name, name=key, timeout=timeout)
        else:
            hwnd = key
        self.HWND = hwnd
        if resize:
            self.auto_resize()
        self.control = uia.ControlFromHandle(hwnd)
        if self.control is not None:
            chatbox_control = self.control.\
                GroupControl(ClassName="mmui::ChatMessagePage").\
                CustomControl(ClassName="mmui::XSplitterView")
            self._chat_api = ChatBox(chatbox_control, self)
            self.nickname = self.control.Name

    def __repr__(self):
        return f'<{PROJECT_NAME} - {self.__class__.__name__} object("{self.nickname}")>'

    @property
    def pid(self):
        if not hasattr(self, '_pid'):
            self._pid = self.control.ProcessId
        return self._pid
    
    def auto_resize(self):
        try:
            monitors = get_monitor_info()
            xy = max(monitors, key=lambda x: x['Height'])['Position']
        except:
            xy = (0, 0)
        self.set_window_size(*WxParam.CHAT_WINDOW_SIZE, xy)
    
    def set_window_size(self, width, height, location: tuple=None):
        if location:
            x, y = location
            uia.win32gui.MoveWindow(self.HWND, x, y, width, height, True)
        else:
            uia.win32gui.SetWindowPos(self.HWND, 0, 0, 0, width, height, 6)
    
    def _get_chatbox(
            self, 
            nickname: str=None, 
            exact: bool=False
        ) -> ChatBox:
        return self._chat_api
    
    def _get_windows(self):
        wins = []
        for hwnd in get_windows_by_pid(self.pid):
            try:
                wins.append(uia.ControlFromHandle(hwnd))
            except:
                pass
        ignore_cls = ['basepopupshadow', 'popupshadow']
        return [win for win in wins if win.ClassName not in ignore_cls]
    
    def chat_info(self):
        return self._chat_api.get_info()
    
    def send_msg(
            self, 
            msg: str,
            who: str=None,
            clear: bool=True, 
            at: Union[str, List[str]]=None,
            exact: bool=False,
        ) -> WxResponse:
        chatbox = self._get_chatbox(who, exact)
        if chatbox is None:
            return WxResponse.failure(f"未找到聊天窗口：{who}")
        return chatbox.send_msg(msg, clear, at)
    
    def send_files(
            self, 
            filepath, 
            who=None, 
            exact=False
        ) -> WxResponse:
        chatbox = self._get_chatbox(who, exact)
        if chatbox is None:
            return WxResponse.failure(f"未找到聊天窗口：{who}")
        return chatbox.send_file(filepath)
    
    def get_msgs(self):
        chatbox = self._get_chatbox()
        if chatbox:
            return chatbox.get_msgs()
        return []
    
    def get_new_msgs(self):
        return self._get_chatbox().get_new_msgs()


version_error_msg = """
错误：未找到可用的微信窗口

wxauto4项目目前仅适用于4.0.5.x版本客户端
下载链接：https://github.com/SiverKing/wechat4.0-windows-versions/releases/download/v4.0.5.26/weixin_4.0.5.26.exe
"""

class WeChatMainWnd(WeChatSubWnd):
    _ui_cls_name: str = 'mmui::MainWindow'
    _win_cls_name: str = 'Qt51514QWindowIcon'
    _ui_name: str = '微信'

    def __init__(self, nickname: str = None, hwnd: int = None):
        self.root = self
        self.parent = self
        if hwnd:
            self._setup_ui(hwnd)
        else:
            wxs = [i for i in GetAllWindows() if i[1] == self._win_cls_name]
            if len(wxs) == 0:
                raise Exception(version_error_msg)
            for index, (hwnd, clsname, winname) in enumerate(wxs):
                self._setup_ui(hwnd)
                if self.control.ClassName == self._ui_cls_name:
                    break
                elif index+1 == len(wxs):
                    raise Exception(version_error_msg)
        # if NetErrInfoTipsBarWnd(self):
        #     raise NetWorkError('微信无法连接到网络')
        
        print(f'初始化成功，获取到已登录窗口：{self.nickname}')

    def _setup_ui(self, hwnd: int):
        self.HWND = hwnd
        self.control = uia.ControlFromHandle(hwnd)
        if self.control is not None:
            navigation_control = self.control.\
                ToolBarControl(ClassName="mmui::MainTabBar", AutomationId='main_tabbar')
            sessionbox_control = self.control.\
                GroupControl(ClassName="mmui::ChatMasterView")
            chatbox_control = self.control.\
                GroupControl(ClassName="mmui::ChatMessagePage").\
                CustomControl(ClassName="mmui::XSplitterView")
            self._navigation_api = NavigationBox(navigation_control, self)
            self._session_api = SessionBox(sessionbox_control, self)
            self._chat_api = ChatBox(chatbox_control, self)
            self.nickname = self.control.Name

    def __repr__(self):
        return f'<{PROJECT_NAME} - {self.__class__.__name__} object("{self.nickname}")>'

    def _get_wx_path(self):
        return GetPathByHwnd(self.HWND)
    
    def _get_wx_dir(self):
        wxdir = os.path.dirname(self._get_wx_path())
        for d in os.listdir(wxdir):
            if re.match('\d+\.\d+\.\d+\.\d+', d):
                return os.path.join(wxdir, d)

    def _get_chatbox(
            self, 
            nickname: str=None, 
            exact: bool=False
        ) -> ChatBox:
        if nickname and (chatbox := WeChatSubWnd(nickname, self, timeout=0)).control:
            return chatbox._chat_api
        else:
            if nickname:
                switch_result = self._session_api.switch_chat(keywords=nickname, exact=exact)
                if not switch_result:
                    return None
            if self._chat_api.msgbox.Exists(0.5):
                return self._chat_api

    def switch_chat(
            self, 
            keywords: str, 
            exact: bool = True,
            force: bool = False,
            force_wait: Union[float, int] = 0.5
        ):
        return self._session_api.switch_chat(keywords, exact, force, force_wait)
        
    def get_all_sub_wnds(self):
        sub_wxs = GetAllWindows(classname=WeChatSubWnd._win_cls_name)
        return [
            sub_win 
            for i in sub_wxs 
            if (
                uia.ControlFromHandle(i[0]).ClassName == WeChatSubWnd._ui_cls_name
                and (sub_win:= WeChatSubWnd(i[0], self)).pid == self.pid
            )
        ]
    
    def get_sub_wnd(self, who: str):
        subwins = self.get_all_sub_wnds()
        for subwin in subwins:
            if subwin.nickname == who:
                return subwin
            
    def open_separate_window(self, keywords: str, resize=True) -> WeChatSubWnd:
        if subwin := self.get_sub_wnd(keywords):
            wxlog.debug(f"{keywords} 获取到已存在的子窗口: {subwin}")
            return subwin
        if nickname := self._session_api.switch_chat(keywords):
            wxlog.debug(f"{keywords} 切换到聊天窗口: {nickname}")
            if subwin := self.get_sub_wnd(nickname):
                wxlog.debug(f"{nickname} 获取到已存在的子窗口: {subwin}")
                return subwin
            else:
                keywords = nickname
        if result := self._session_api.open_separate_window(keywords):
            find_nickname = result['data'].get('nickname', keywords)
            return WeChatSubWnd(find_nickname, self, resize=resize)