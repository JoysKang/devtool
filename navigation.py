import flet as ft
from typing import Callable, Dict
from views.json_formatter import JsonFormatterView


class Navigation:
    """导航栏管理类"""
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_view = None
        # 注册所有可用的视图
        self.views: Dict[str, Callable] = {
            "json_formatter": lambda: JsonFormatterView(self.page),
            # 后续在这里添加更多视图
        }
        
        self.setup_layout()

    def setup_layout(self):
        """设置主布局"""
        # 创建导航栏
        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=80,
            min_extended_width=150,
            group_alignment=-0.9,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.icons.DATA_OBJECT,
                    selected_icon=ft.icons.DATA_OBJECT,
                    label="JSON格式化",
                ),
                ft.NavigationRailDestination(
                    icon=ft.icons.CONSTRUCTION,
                    selected_icon=ft.icons.CONSTRUCTION,
                    label="开发中...",
                ),
            ],
            on_change=self.nav_change,
        )

        # 创建内容区
        self.content_area = ft.Container(
            expand=True,
        )

        # 设置主布局
        self.page.add(
            ft.Row(
                [
                    self.nav_rail,
                    ft.VerticalDivider(width=1),
                    self.content_area,
                ],
                expand=True,
            )
        )

        # 默认显示第一个视图
        self.show_view("json_formatter")

    def nav_change(self, e):
        """处理导航切换"""
        index_to_view = {
            0: "json_formatter",
            # 后续添加更多映射
        }
        
        view_name = index_to_view.get(e.control.selected_index)
        if view_name:
            self.show_view(view_name)
        else:
            self.content_area.content = ft.Text("功能开发中...")
        self.page.update()

    def show_view(self, view_name: str):
        """显示指定视图"""
        if view_name in self.views:
            # 清理当前视图
            if self.current_view:
                self.content_area.content = None
            
            # 创建并显示新视图
            view = self.views[view_name]()
            self.content_area.content = view.build()
            self.current_view = view
            self.page.update()
