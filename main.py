import flet as ft
from navigation import Navigation


def main(page: ft.Page):
    # 设置页面基本属性
    page.title = "多功能工具箱"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1200
    page.window.height = 800
    
    # 初始化导航
    Navigation(page)


if __name__ == "__main__":
    ft.app(target=main)
