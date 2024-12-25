import flet as ft
import json
import re
from typing import List
from dataclasses import dataclass
import json5
import rapidjson
import unittest
import json_repair


@dataclass
class JsonLine:
    """表示JSON的一行内容"""

    text: str  # 行文本内容
    level: int  # 缩进级别
    has_error: bool  # 是否包含错误
    error_message: str | None  # 错误信息


@dataclass
class JsonAnalyzerConfig:
    indent: int | None = 2
    ensure_ascii: bool = False
    max_error_context: int = 20
    show_line_numbers: bool = True
    separators: tuple[str, str] | None = None  # 添加 separators 配置


class JsonAnalyzer:
    def __init__(self, config: JsonAnalyzerConfig = None):
        self.config = config or JsonAnalyzerConfig()

    def analyze_json(self, text: str) -> List[JsonLine]:
        """
        分析JSON文本并返回格式化结果
        使用到了 rapidjson(快速格式化)、json5(处理不规范格式)、json_repair(修复不完整JSON) 三个库

        优化点:
        1. 预检查减少不必要的解析
        2. 使用更高效的解析方式
        3. 保证对大文件的处理能力

        Args:
            text: 要分析的JSON文本

        Returns:
            List[JsonLine]: 格式化后的行列表
        """
        # 预检查输入
        if not text or not text.strip():
            return [JsonLine(text="", level=0, has_error=True, error_message="空输入")]

        # 预定义 rapidjson.dumps 的通用参数
        dump_kwargs = {
            "indent": self.config.indent,
            "ensure_ascii": self.config.ensure_ascii,
        }

        # 如果是压缩模式
        if self.config.separators:
            dump_kwargs["indent"] = None  # rapidjson 使用 indent=None 来压缩输出

        try:
            # 对于大文件，rapidjson的性能最好
            parsed = rapidjson.loads(text)
            return self._create_success_lines(rapidjson.dumps(parsed, **dump_kwargs))
        except rapidjson.JSONDecodeError as e:
            original_error = e

        # 1. 快速检查是否为标准JSON格式
        first_char = text.lstrip()[0]
        last_char = text.rstrip()[-1]
        is_potential_json = (
            (first_char in "{[" and last_char in "}]")
            or (first_char in '"' and last_char in '"')
            or text.strip().lower() in ("true", "false", "null")
            or text.strip().replace(".", "", 1).isdigit()
        )

        if is_potential_json:
            # 2. rapidjson解析（最快）
            try:
                # 对于大文件，rapidjson的性能最好
                parsed = rapidjson.loads(text)
                return self._create_success_lines(
                    rapidjson.dumps(parsed, **dump_kwargs)
                )
            except rapidjson.JSONDecodeError as e:
                original_error = e
        else:
            original_error = None

        # 3. json5解析（处理不规范格式）
        try:
            parsed = json5.loads(text)
            return self._create_success_lines(rapidjson.dumps(parsed, **dump_kwargs))
        except Exception:
            # 4. json_repair尝试修复
            try:
                repaired = json_repair.repair_json(text)
                if repaired:
                    # 使用rapidjson验证和格式化
                    parsed = rapidjson.loads(repaired)
                    return self._create_success_lines(
                        rapidjson.dumps(parsed, **dump_kwargs)
                    )
            except Exception:
                # 5. 错误处理逻辑
                if original_error:
                    return self._handle_error(text, original_error)
                else:
                    # 创建一个通用错误信息
                    return [
                        JsonLine(
                            text=text,  # 保留完整文本
                            level=0,
                            has_error=True,
                            error_message="无法解析的JSON格式",
                        )
                    ]

    def _handle_error(
        self, text: str, error: rapidjson.JSONDecodeError
    ) -> List[JsonLine]:
        """处理JSON解析错误，尝试找到最后一个有效的JSON片段"""
        lines = []
        try:
            # 从错误信息中提取位置
            error_str = str(error)
            offset_match = re.search(r"at offset (\d+):", error_str)
            if not offset_match:
                raise ValueError("无法解析错误位置")

            error_pos = int(offset_match.group(1))
            text_before_error = text[:error_pos]

            # 从错误位置向前查找有效的JSON片段
            valid_json = self._find_valid_json_before_position(text_before_error)

            if valid_json:
                # 格式化有效部分
                try:
                    parsed = rapidjson.loads(valid_json)
                    formatted = json.dumps(
                        parsed,
                        indent=self.config.indent,
                        ensure_ascii=self.config.ensure_ascii,
                    )
                    lines.extend(self._create_success_lines(formatted))
                except:
                    pass

            # 添加错误信息
            error_context = text[error_pos : error_pos + self.config.max_error_context]
            lines.append(
                JsonLine(
                    text=error_context,
                    level=0,
                    has_error=True,
                    error_message=f"解析错误 (位置 {error_pos}): {error_str}",
                )
            )

        except Exception as e:
            lines.append(
                JsonLine(
                    text=text,
                    level=0,
                    has_error=True,
                    error_message=f"处理错误: {str(e)}",
                )
            )

        return lines

    def _find_valid_json_before_position(self, text: str) -> str:
        """
        从给定文本中查找并修复最后一个有效的JSON片段
        使用 json_repair 来修复不完整的 JSON

        Args:
            text: 要处理的文本

        Returns:
            str: 修复后的JSON字符串,如果无法修复则返回空字符串
        """
        if not text.strip():
            return ""

        # 找出所有逗号的位置
        comma_positions = [pos for pos, char in enumerate(text) if char == ","]
        if not comma_positions:
            # 如果没有逗号,尝试修复整个文本
            try:
                return json_repair.repair_json(text)
            except:
                return ""

        # 从后向前尝试每个逗号位置
        for pos in reversed(comma_positions):
            try_text = text[:pos]
            if not try_text.strip():
                continue

            try:
                # 使用 json_repair 尝试修复
                repaired = json_repair.repair_json(try_text)
                if repaired:  # 如果修复成功
                    return repaired
            except:
                continue

        return ""

    def _create_success_lines(self, formatted_json: str) -> List[JsonLine]:
        """创建格式化的JSON行"""
        lines = []
        level = 0

        for line in formatted_json.splitlines():
            # 计算缩进级别
            stripped = line.lstrip()
            if stripped.startswith("}") or stripped.startswith("]"):
                level -= 1

            lines.append(
                JsonLine(text=line, level=level, has_error=False, error_message=None)
            )

            if stripped.endswith("{") or stripped.endswith("["):
                level += 1

        return lines

    def _complete_json(self, partial_json: str) -> str:
        """尝试补全不完整的JSON结构"""
        if not partial_json:
            return ""

        try:
            stack = []
            in_string = False
            escape = False

            for char in partial_json:
                if not in_string:
                    if char in "{[":
                        stack.append(char)
                    elif char in "}]":
                        if stack and (
                            (stack[-1] == "{" and char == "}")
                            or (stack[-1] == "[" and char == "]")
                        ):
                            stack.pop()

                # 处理字符串
                if char == '"' and not escape:
                    in_string = not in_string
                escape = char == "\\" and not escape

            # 补全缺失的括号
            completion = ""
            for bracket in reversed(stack):
                completion += "}" if bracket == "{" else "]"

            return partial_json + completion
        except Exception:
            return partial_json  # 如果补全失败，返回原始文本


class JsonFormatterView:
    """JSON格式化器视图"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.setup_controls()

    def setup_controls(self):
        """初始化控件"""
        # 添加缩进控制下拉菜单
        self.indent_dropdown = ft.Dropdown(
            label="缩进",
            value="4",  # 默认值
            options=[
                ft.dropdown.Option("compact", "压缩"),
                ft.dropdown.Option("2", "2 空格"),
                ft.dropdown.Option("4", "4 空格"),
            ],
            on_change=self.on_indent_change,
            width=150,
            height=35,
            border_radius=8,
            filled=True,
            focused_border_color=ft.colors.BLUE_400,
            focused_bgcolor=ft.colors.BLUE_50,
            text_style=ft.TextStyle(
                font_family="monospace",
                color=ft.colors.BLUE_GREY_900,
                size=12,
            ),
            content_padding=ft.padding.only(left=10, top=0, right=10, bottom=0),
            item_height=48,
        )

        # 创建输入区域
        self.input_text = ft.TextField(
            multiline=True,
            min_lines=None,
            value="",
            hint_text="在此粘贴您的JSON数据...",
            hint_style=ft.TextStyle(
                color=ft.colors.GREY_400,
                italic=True,
            ),
            text_style=ft.TextStyle(
                font_family="monospace",  # 使用等宽字体
                size=14,
            ),
            on_change=self.on_input_change,
            expand=True,
            border=ft.InputBorder.NONE,
            text_align=ft.TextAlign.LEFT,
        )

        # 输出区域
        self.output_container = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
            width=float("inf"),
        )

        self.error_text = ft.Text(color=ft.Colors.RED, visible=False)

        # 创建 JsonAnalyzer 实例并设置初始配置
        self.analyzer = JsonAnalyzer(JsonAnalyzerConfig(indent=4))

        # 创建图标按钮
        button_padding = 2  # 减小 padding 值

        # 创建按钮时使用更小的 padding
        button_style = {
            "icon_color": ft.colors.BLUE_GREY_400,
            "icon_size": 20,
            "padding": button_padding,
        }

        self.input_paste_button = ft.IconButton(
            icon=ft.icons.CONTENT_PASTE,
            tooltip="粘贴",
            on_click=self.handle_paste,
            **button_style,
        )

        self.input_copy_button = ft.IconButton(
            icon=ft.icons.CONTENT_COPY,
            tooltip="复制",
            on_click=lambda _: self.handle_copy(self.input_text.value),
            **button_style,
        )

        self.input_search_button = ft.IconButton(
            icon=ft.icons.SEARCH,
            tooltip="搜索",
            on_click=self.handle_input_search,
            **button_style,
        )

        self.output_copy_button = ft.IconButton(
            icon=ft.icons.CONTENT_COPY,
            tooltip="复制",
            on_click=lambda _: self.handle_copy(self.get_output_text()),
            **button_style,
        )

        self.output_search_button = ft.IconButton(
            icon=ft.icons.SEARCH,
            tooltip="搜索",
            on_click=self.handle_output_search,
            **button_style,
        )

    def build(self) -> ft.Control:
        """构建视图"""
        return ft.Column(
            [
                # 标题栏
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(
                                "JSON格式化",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=ft.colors.BLUE_GREY_900,
                            ),
                            self.indent_dropdown,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ),
                # 主要内容区
                ft.Row(
                    [
                        # 左侧输入区域
                        ft.Column(
                            [
                                # 输入框顶部工具栏
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.Container(width=1, expand=True),  # 占位
                                            # 使用 Stack 来紧密排列按钮
                                            ft.Stack(
                                                [
                                                    self.input_paste_button,
                                                    ft.Container(
                                                        margin=ft.margin.only(left=30),
                                                        content=self.input_copy_button,
                                                    ),
                                                    ft.Container(
                                                        margin=ft.margin.only(left=60),
                                                        content=self.input_search_button,
                                                    ),
                                                ],
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                    padding=ft.padding.only(bottom=0),
                                ),
                                # 输入框容器
                                ft.Container(
                                    content=self.input_text,
                                    border=ft.border.all(1.5, ft.colors.BLUE_GREY_100),
                                    border_radius=12,
                                    padding=20,
                                    expand=True,
                                    bgcolor=ft.colors.WHITE,
                                    shadow=ft.BoxShadow(
                                        spread_radius=1,
                                        blur_radius=5,
                                        color=ft.colors.with_opacity(
                                            0.1, ft.colors.BLUE_GREY_300
                                        ),
                                    ),
                                ),
                            ],
                            expand=True,
                            spacing=0,  # 减小列内元素间距
                        ),
                        # 右侧输出区域
                        ft.Column(
                            [
                                # 输出框顶部工具栏
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.Container(width=1, expand=True),  # 占位
                                            # 使用 Stack 来紧密排列按钮
                                            ft.Stack(
                                                [
                                                    self.output_copy_button,
                                                    ft.Container(
                                                        margin=ft.margin.only(left=30),
                                                        content=self.output_search_button,
                                                    ),
                                                ],
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                    padding=ft.padding.only(bottom=0),
                                ),
                                # 输出框容器
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            self.error_text,
                                            self.output_container,
                                        ],
                                        spacing=10,
                                    ),
                                    border=ft.border.all(1.5, ft.colors.BLUE_GREY_100),
                                    border_radius=12,
                                    padding=20,
                                    expand=True,
                                    bgcolor=ft.colors.WHITE,
                                    shadow=ft.BoxShadow(
                                        spread_radius=1,
                                        blur_radius=5,
                                        color=ft.colors.with_opacity(
                                            0.1, ft.colors.BLUE_GREY_300
                                        ),
                                    ),
                                ),
                            ],
                            expand=True,
                            spacing=0,  # 减小列内元素间距
                        ),
                    ],
                    expand=True,
                    spacing=20,
                ),
            ],
            expand=True,
            spacing=20,
            width=float("inf"),
        )

    def on_indent_change(self, e):
        """缩进值改变时的处理"""
        value = self.indent_dropdown.value
        if value == "compact":
            # 压缩模式：使用 indent=None
            self.analyzer.config.indent = None
            self.analyzer.config.separators = (
                ",",
                ":",
            )  # 保留这个标记，但实际使用 indent=None
        else:
            # 正常缩进模式
            self.analyzer.config.indent = int(value)
            self.analyzer.config.separators = None

        # 重新格式化当前输入
        if self.input_text.value:
            self.on_input_change(None)

    def on_input_change(self, e):
        """输入改变时的处理"""
        self.output_container.controls.clear()

        if not self.input_text.value.strip():
            return

        try:
            lines = self.analyzer.analyze_json(self.input_text.value)
            for line in lines:
                text_color = (
                    ft.colors.RED_500 if line.has_error else ft.colors.BLUE_GREY_900
                )

                # 创建行容器
                line_container = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                "  " * line.level + line.text,
                                color=text_color,
                                size=14,
                                font_family="monospace",
                                weight=ft.FontWeight.NORMAL,
                            )
                        ]
                    ),
                    padding=ft.padding.symmetric(vertical=3),
                    border_radius=4,
                )

                if line.has_error:
                    line_container.content.controls.append(
                        ft.Text(
                            f"← {line.error_message}",
                            color=ft.colors.RED_400,
                            size=12,
                            italic=True,
                            weight=ft.FontWeight.NORMAL,
                        )
                    )

                self.output_container.controls.append(line_container)

        except Exception as e:
            self.error_text.value = f"解析错误: {str(e)}"
            self.error_text.visible = True
            self.error_text.color = ft.colors.RED_400

        self.page.update()

    # 添加处理函数
    async def handle_paste(self, e):
        """处理粘贴操作"""
        text = await self.page.get_clipboard()
        if text:
            self.input_text.value = text
            self.on_input_change(None)
            self.page.update()

    def handle_copy(self, text: str):
        """处理复制操作"""
        self.page.set_clipboard(text)
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("已复制到剪贴板")))

    def handle_input_search(self, e):
        """处理输入框搜索"""
        # TODO: 实现输入框搜索功能
        pass

    def handle_output_search(self, e):
        """处理输出框搜索"""
        # TODO: 实现输出框搜索功能
        pass

    def get_output_text(self) -> str:
        """获取输出文本内容"""
        return "\n".join(
            control.content.controls[0].value
            for control in self.output_container.controls
            if isinstance(control, ft.Container)
        )


class TestJsonAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = JsonAnalyzer()

    def test_valid_json(self):
        json_str = '{"name": "test"}'
        result = self.analyzer.analyze_json(json_str)
        self.assertFalse(any(line.has_error for line in result))

    def test_invalid_json(self):
        json_str = '{"name": "test"'
        result = self.analyzer.analyze_json(json_str)
        self.assertTrue(any(line.has_error for line in result))
