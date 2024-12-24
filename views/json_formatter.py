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
    text: str            # 行文本内容
    level: int          # 缩进级别
    has_error: bool     # 是否包含错误
    error_message: str | None  # 错误信息


@dataclass
class JsonAnalyzerConfig:
    indent: int = 2
    ensure_ascii: bool = False
    max_error_context: int = 20
    show_line_numbers: bool = True
    

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
        
        # 预定义json.dumps的通用参数
        dump_kwargs = {
            'indent': self.config.indent,
            'ensure_ascii': self.config.ensure_ascii
        }
        
        # 1. 快速检查是否为标准JSON格式
        first_char = text.lstrip()[0]
        last_char = text.rstrip()[-1]
        is_potential_json = (
            (first_char in '{[' and last_char in '}]') or
            (first_char in '"' and last_char in '"') or
            text.strip().lower() in ('true', 'false', 'null') or
            text.strip().replace('.','',1).isdigit()
        )
        
        if is_potential_json:
            # 2. rapidjson解析（最快）
            try:
                # 对于大文件，rapidjson的性能最好
                parsed = rapidjson.loads(text)
                return self._create_success_lines(
                    rapidjson.dumps(parsed, **dump_kwargs)  # 使用rapidjson.dumps替代json.dumps
                )
            except rapidjson.JSONDecodeError as e:
                original_error = e
        else:
            original_error = None
        
        # 3. json5解析（处理不规范格式）
        try:
            parsed = json5.loads(text)
            return self._create_success_lines(
                rapidjson.dumps(parsed, **dump_kwargs)
            )
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
                    return [JsonLine(
                        text=text,  # 保留完整文本
                        level=0,
                        has_error=True,
                        error_message="无法解析的JSON格式"
                    )]

    def _handle_error(self, text: str, error: rapidjson.JSONDecodeError) -> List[JsonLine]:
        """处理JSON解析错误，尝试找到最后一个有效的JSON片段"""
        lines = []
        try:
            # 从错误信息中提取位置
            error_str = str(error)
            offset_match = re.search(r'at offset (\d+):', error_str)
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
                    formatted = json.dumps(parsed, indent=self.config.indent, ensure_ascii=self.config.ensure_ascii)
                    lines.extend(self._create_success_lines(formatted))
                except:
                    pass
            
            # 添加错误信息
            error_context = text[error_pos:error_pos + self.config.max_error_context]
            lines.append(JsonLine(
                text=error_context,
                level=0,
                has_error=True,
                error_message=f"解析错误 (位置 {error_pos}): {error_str}"
            ))
            
        except Exception as e:
            lines.append(JsonLine(
                text=text,
                level=0,
                has_error=True,
                error_message=f"处理错误: {str(e)}"
            ))
        
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
        comma_positions = [pos for pos, char in enumerate(text) if char == ',']
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
            if stripped.startswith('}') or stripped.startswith(']'):
                level -= 1
                
            lines.append(JsonLine(
                text=line,
                level=level,
                has_error=False,
                error_message=None
            ))
            
            if stripped.endswith('{') or stripped.endswith('['):
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
                    if char in '{[':
                        stack.append(char)
                    elif char in '}]':
                        if stack and ((stack[-1] == '{' and char == '}') or 
                                    (stack[-1] == '[' and char == ']')):
                            stack.pop()
                
                # 处理字符串
                if char == '"' and not escape:
                    in_string = not in_string
                escape = char == '\\' and not escape
                        
            # 补全缺失的括号
            completion = ''
            for bracket in reversed(stack):
                completion += '}' if bracket == '{' else ']'
                
            return partial_json + completion
        except Exception:
            return partial_json  # 如果补全失败，返回原始文本


class JsonFormatterView:
    """JSON格式化器视图"""
    def __init__(self, page: ft.Page):
        self.page = page
        self.analyzer = JsonAnalyzer()  # 使用原有的JsonAnalyzer
        self.setup_controls()

    def setup_controls(self):
        """初始化控件"""
        # 创建输入区域
        self.input_text = ft.TextField(
            multiline=True,
            min_lines=10,
            max_lines=15,
            value="",
            label="输入JSON",
            hint_text="在此粘贴您的JSON数据...",
            on_change=self.on_input_change,
            expand=True,
        )

        # 创建格式化按钮
        self.format_button = ft.ElevatedButton(
            "格式化",
            on_click=self.format_json,
            style=ft.ButtonStyle(
                color={ft.ControlState.DEFAULT: ft.Colors.WHITE},
                bgcolor={ft.ControlState.DEFAULT: ft.Colors.BLUE},
            ),
        )

        # 创建输出区域
        self.output_container = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )

        # 创建错误提示区域
        self.error_text = ft.Text(color=ft.Colors.RED, visible=False)

    def build(self) -> ft.Control:
        """构建视图"""
        return ft.Column(
            [
                ft.Text("JSON格式化", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=self.input_text,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    border_radius=10,
                    padding=10,
                    expand=True,
                ),
                ft.Row(
                    [
                        self.format_button,
                        ft.TextButton("清空", on_click=self.clear_input),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                self.error_text,
                ft.Container(
                    content=self.output_container,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    border_radius=10,
                    padding=10,
                    expand=True,
                    bgcolor=ft.Colors.GREY_50,
                ),
            ],
            expand=True,
            spacing=20,
        )

    def on_input_change(self, e):
        """输入改变时的处理"""
        self.clear_output()

        if self.input_text.value:
            pass

    def clear_input(self, e=None):
        """清空输入"""
        self.input_text.value = ""
        self.clear_output()
        self.page.update()

    def clear_output(self):
        """清空输出"""
        self.output_container.controls.clear()
        self.error_text.visible = False
        self.page.update()

    def format_json(self, e):
        """格式化JSON"""
        self.clear_output()

        if not self.input_text.value.strip():
            self.error_text.value = "请输入JSON数据"
            self.error_text.visible = True
            self.page.update()
            return

        try:
            # 分析JSON
            lines = self.analyzer.analyze_json(self.input_text.value)

            # 显示格式化结果
            has_errors = False
            for line in lines:
                text_color = ft.Colors.RED if line.has_error else ft.Colors.BLACK

                # 创建行容器
                line_container = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                "  " * line.level + line.text,
                                color=text_color,
                                size=14,
                                font_family="monospace",
                            )
                        ]
                    ),
                    padding=ft.padding.symmetric(vertical=2),
                )

                # 如果有错误，添加错误信息
                if line.has_error:
                    has_errors = True
                    line_container.content.controls.append(
                        ft.Text(
                            f"← {line.error_message}",
                            color=ft.Colors.RED,
                            size=12,
                            italic=True,
                        )
                    )

                self.output_container.controls.append(line_container)

            if not has_errors:
                # 尝试美化输出
                try:
                    parsed = json.loads(self.input_text.value)
                    self.input_text.value = json.dumps(
                        parsed, indent=self.analyzer.config.indent, ensure_ascii=self.analyzer.config.ensure_ascii
                    )
                except:
                    pass

        except Exception as e:
            self.error_text.value = f"解析错误: {str(e)}"
            self.error_text.visible = True

        self.page.update()


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
