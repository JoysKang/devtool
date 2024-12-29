import flet as ft
from navigation import Navigation

def main():
    def app(page: ft.Page):
        # 配置页面
        page.title = "JSON格式化工具"
        page.window.width = 1200
        page.window.height = 800
        page.window.min_width = 800
        page.window.min_height = 600
        page.padding = 20
        page.theme_mode = ft.ThemeMode.LIGHT
        page.bgcolor = ft.Colors.BLUE_GREY_50
        
        # 创建导航
        Navigation(page)

    ft.app(target=app, assets_dir="assets")

if __name__ == "__main__":
    main()
