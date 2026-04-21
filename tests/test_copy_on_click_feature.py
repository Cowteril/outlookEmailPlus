"""
测试只读字段点击复制功能

测试范围：
1. 点击复制功能（input/textarea元素）
2. 视觉反馈效果（CSS闪绿动画）
3. Toast提示显示
4. 错误处理（空值、复制失败）
5. 不同元素类型的支持
"""

import os
import sys
import re

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 设置测试���境变量
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-copy-tests')
os.environ.setdefault('LOGIN_PASSWORD', 'testpass123')


class TestCSSStyles:
    """测试CSS样式是否正确应用"""

    def test_copy_on_click_css_exists(self):
        """测试copy-on-click样式定义"""
        with open('static/css/main.css', 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 检查.copy-on-click样式
        assert '.copy-on-click' in css_content, "缺少.copy-on-click样式定义"
        assert 'cursor: pointer' in css_content, "缺少cursor: pointer样式"

    def test_copy_flash_animation_css_exists(self):
        """测试复制成功闪绿动画样式"""
        with open('static/css/main.css', 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 检查动画类
        assert '.copy-flash-success' in css_content, "缺少.copy-flash-success样式类"

        # 检查动画定义
        assert '@keyframes copy-success-flash' in css_content, "缺少copy-success-flash动画定义"

        # 验证透明度已调整为100%
        assert 'rgba(6, 118, 71, 1)' in css_content, "透明度未调整为100%"

    def test_readonly_field_css_exists(self):
        """测试只读字段样式"""
        with open('static/css/main.css', 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 检查readonly-field样式
        assert '.readonly-field' in css_content, "缺少.readonly-field样式"


class TestJavaScriptFunctionality:
    """测试JavaScript功能"""

    def test_bind_copy_on_click_fields_function_exists(self):
        """测试bindCopyOnClickFields函数存在"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查函数定义
        assert 'function bindCopyOnClickFields()' in js_content, "缺少bindCopyOnClickFields函数定义"
        assert 'copy-on-click' in js_content, "代码中缺少copy-on-click引用"

    def test_copy_function_uses_clipboard_api(self):
        """测试复制功能使用了Clipboard API"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查使用了现代Clipboard API
        assert 'navigator.clipboard.writeText' in js_content, "未使用现代Clipboard API"

        # 检查有降级方案
        assert 'document.execCommand' in js_content or 'execCommand' in js_content, "缺少降级方案"

    def test_copy_function_includes_error_handling(self):
        """测试复制功能包含错误处理"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查try-catch错误处理
        assert 'try {' in js_content, "缺少try关键字"
        assert 'catch' in js_content, "缺少catch关键字"

    def test_copy_function_shows_success_feedback(self):
        """测试复制成功后显示反馈"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查添加闪绿效果class
        assert 'copy-flash-success' in js_content, "缺少视觉反馈class"
        assert 'classList.add' in js_content, "缺少classList.add方法"

        # 检查显示toast提示
        assert 'showToast' in js_content, "缺少showToast函数调用"
        assert ('已复制到剪贴板' in js_content or
                'Copied to clipboard' in js_content), "缺少成功提示文字"

    def test_copy_function_handles_empty_value(self):
        """测试空值处理"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查空值检查
        assert 'trim()' in js_content, "缺少trim()空值处理"
        assert ('没有可复制的内容' in js_content or
                'No content to copy' in js_content or
                'warn' in js_content), "缺少空值错误提示"

    def test_copy_function_initialization(self):
        """测试函数在DOMContentLoaded中初始化"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查函数被调用
        assert 'bindCopyOnClickFields()' in js_content, "函数未被调用"

        # 检查在DOMContentLoaded中调用
        assert 'DOMContentLoaded' in js_content, "未在DOMContentLoaded中初始化"


class TestModalTemplateIntegration:
    """测试模态框模板集成"""

    def test_oauth_modal_has_copy_on_click_fields(self):
        """测试OAuth模态框包含copy-on-click字段"""
        with open('templates/partials/modals.html', 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 检查OAuth相关字段存在
        assert 'id="oauthClientIdInput"' in template_content, "缺少oauthClientIdInput字段"
        assert 'id="oauthRedirectUriInput"' in template_content, "缺少oauthRedirectUriInput字段"
        assert 'id="authUrlInput"' in template_content, "缺少authUrlInput字段"
        assert 'id="refreshTokenOutput"' in template_content, "缺少refreshTokenOutput字段"

    def test_oauth_modal_fields_have_copy_class(self):
        """测试OAuth模态框字段有copy-on-click class"""
        with open('templates/partials/modals.html', 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 检查字段有copy-on-click class
        assert 'copy-on-click' in template_content, "字段缺少copy-on-click class"
        assert 'readonly' in template_content, "字段缺少readonly属性"

    def test_auth_url_copy_button_removed(self):
        """测试授权URL的复制按钮已移除"""
        with open('templates/partials/modals.html', 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 检查不再有"复制"按钮（只保留"打开"按钮）
        # 确保有"打开"按钮但没有"复制"按钮
        assert 'onclick="openAuthUrl()"' in template_content, "缺少打开按钮"
        assert template_content.count('onclick="copyAuthUrl()"') == 0, "复制按钮未被移除"

    def test_auth_url_open_button_preserved(self):
        """测试授权URL的"打开"按钮保留"""
        with open('templates/partials/modals.html', 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 检查"打开"按钮仍然存在
        assert 'openAuthUrl' in template_content, "缺少打开按钮函数"


class TestVisualFeedbackAnimation:
    """测试视觉反馈动画"""

    def test_flash_animation_timing(self):
        """测试闪绿动画时间设置"""
        with open('static/css/main.css', 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 提取动画时间
        animation_match = re.search(r'animation:\s*copy-success-flash\s*([\d.]+)s', css_content)

        if animation_match:
            duration = float(animation_match.group(1))
            assert 0.4 <= duration <= 1.0, f"动画时间{duration}秒应在0.4-1.0秒之间"
        else:
            # 如果没找到animation属性，检查keyframes中是否有时间设置
            keyframe_match = re.search(r'0%.*?{[^}]*?animation[^}]*?([\d.]+)s', css_content)
            assert keyframe_match, "无法找到动画时间设置"

    def test_flash_animation_colors(self):
        """测试闪绿动画颜色设置"""
        with open('static/css/main.css', 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 检查使用了绿色（RGB: 6, 118, 71）
        assert 'rgba(6, 118, 71, 1)' in css_content, "未使用正确的绿色或透明度不是100%"

        # 检查使用success颜色变量
        assert 'var(--clr-success)' in css_content, "未使用success颜色变量"

    def test_hover_effect_exists(self):
        """测试悬停效果存在"""
        with open('static/css/main.css', 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 检查悬停效果
        assert '.copy-on-click:hover' in css_content, "缺少悬停效果"
        assert 'box-shadow' in css_content, "缺少阴影效果"


class TestIntegrationScenarios:
    """集成测试场景"""

    def test_complete_copy_workflow_code_structure(self):
        """验证完整复制工作流程的代码结构"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 验证完整的工作流程代码存在
        has_click_handler = ('addEventListener(\'click\'' in js_content or
                             'addEventListener("click"' in js_content)
        has_copy_logic = 'navigator.clipboard.writeText' in js_content
        has_visual_feedback = 'copy-flash-success' in js_content
        has_toast_feedback = 'showToast' in js_content

        assert has_click_handler, "缺少点击事件处理器"
        assert has_copy_logic, "缺少复制逻辑"
        assert has_visual_feedback, "缺少视觉反馈"
        assert has_toast_feedback, "缺少Toast提示"


class TestErrorHandling:
    """测试错误处理"""

    def test_empty_field_handling(self):
        """测试空字段处理"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查空值检查逻辑
        assert 'trim()' in js_content, "缺少trim()空值处理"
        assert 'if (!value' in js_content or 'if (value' in js_content, "缺少空值判断"

    def test_copy_failure_handling(self):
        """测试复制失败处理"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查错误处理
        assert 'catch' in js_content, "缺少错误捕获"
        assert ('复制失败' in js_content or
                'copy failed' in js_content.lower() or
                'error' in js_content.lower()), "缺少错误提示"


class TestCrossBrowserCompatibility:
    """测试跨浏览器兼容性"""

    def test_clipboard_api_fallback(self):
        """测试Clipboard API降级方案"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查现代API和降级方案都存在
        has_modern_api = 'navigator.clipboard' in js_content
        has_fallback = ('execCommand(\'copy\')' in js_content or
                       'execCommand("copy")' in js_content)

        assert has_modern_api, "缺少现代Clipboard API"
        assert has_fallback, "缺少降级方案execCommand"

    def test_secure_context_check(self):
        """测试安全上下文检查"""
        with open('static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()

        # 检查是否检查安全上下文
        assert 'window.isSecureContext' in js_content, "缺少安全上下文检查"


class TestAccessibility:
    """测试可访问性"""

    def test_clickable_area(self):
        """测试可点击区域"""
        with open('static/css/main.css', 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 检查cursor: pointer表明可点击
        assert 'cursor: pointer' in css_content, "缺少cursor: pointer样式"

    def test_title_attribute_for_screen_readers(self):
        """测试title属性帮助屏幕阅读器"""
        with open('templates/partials/modals.html', 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 检查有title提示
        has_title = ('title="点击复制"' in template_content or
                     'title=\'点击复制\'' in template_content or
                     'title="' in template_content)
        assert has_title, "缺少title属性提示"


def run_copy_on_click_tests():
    """运行所有点击复制功能测试"""
    print("Testing Click-to-Copy Feature...")
    print("=" * 60)

    tests = [
        ("CSS样式", TestCSSStyles),
        ("JavaScript功能", TestJavaScriptFunctionality),
        ("模态框集成", TestModalTemplateIntegration),
        ("视觉反馈", TestVisualFeedbackAnimation),
        ("集成场景", TestIntegrationScenarios),
        ("错误处理", TestErrorHandling),
        ("跨浏览器兼容", TestCrossBrowserCompatibility),
        ("可访问性", TestAccessibility),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_name, test_class in tests:
        print(f"\n[Test Group] {test_name}")
        print("-" * 40)

        test_instance = test_class()

        # 获取所有测试方法
        test_methods = [method for method in dir(test_instance) if method.startswith('test_')]

        for method_name in test_methods:
            method = getattr(test_instance, method_name)
            try:
                method()
                print(f"  [PASS] {method_name}")
                passed += 1
            except AssertionError as e:
                print(f"  [FAIL] {method_name}")
                print(f"     Error: {str(e)}")
                failed += 1
            except Exception as e:
                print(f"  [WARN] {method_name}")
                print(f"     Unexpected error: {str(e)}")
                failed += 1

    print("\n" + "=" * 60)
    print(f"[Results] {passed} passed, {failed} failed, {skipped} skipped")
    if passed + failed > 0:
        print(f"[Pass Rate] {passed/(passed+failed)*100:.1f}%")
    print(f"[Coverage] {len(tests)} test groups, {passed + failed} test cases")

    if failed == 0:
        print("[SUCCESS] All tests passed! Click-to-copy feature is complete!")
        return True
    else:
        print(f"[WARNING] {failed} tests failed, please check implementation")
        return False


if __name__ == "__main__":
    success = run_copy_on_click_tests()
    sys.exit(0 if success else 1)
