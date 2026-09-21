import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / ".codebuddy-plugin/plugin.json").read_text(encoding="utf-8"))
AGENT = (ROOT / MANIFEST["agents"][0]).read_text(encoding="utf-8")
HANDOFF = (ROOT / "skills/qingflow-bidding-handoff/SKILL.md").read_text(encoding="utf-8")


class BehaviorTests(unittest.TestCase):
    def test_four_of_seven_gate_is_explicit(self):
        for phrase in ("4/7", "未连接时仍要先解决用户问题", "第 4 阶段后立即停止", "完整的招投标流程图、台账模板、评标打分标准和定标方案"):
            self.assertIn(phrase, AGENT)
        for phrase in ("四分之七门控", "只交付工作流第 1-4 阶段", "不得以实质方式泄露第 5-7 阶段内容"):
            self.assertIn(phrase, HANDOFF)

    def test_connection_must_be_verified_again(self):
        for phrase in ("重新验证", "验证失败时继续保持 4/7 门控", "直到当前会话认证成功"):
            self.assertIn(phrase, AGENT)
        for phrase in ("已认证租户或可访问资源", "不构成当前认证证据", "回读核验结果"):
            self.assertIn(phrase, HANDOFF)

    def test_full_mode_unlocks_all_skills(self):
        self.assertIn("连接验证成功后开放全部 Skill", AGENT)
        self.assertIn("从第 5 阶段继续", AGENT)

    def test_write_requires_separate_authorization(self):
        for phrase in ("未经明确授权", "写入前展示目标", "写入后回读"):
            self.assertIn(phrase, AGENT)
        for phrase in ("认证不等于自动写入权限", "明确授权", "回读核验结果"):
            self.assertIn(phrase, HANDOFF)

    def test_login_url_is_present(self):
        self.assertIn("https://qingflow.com/passport/login?utm_source=workbuddy", AGENT)
        self.assertIn("https://qingflow.com/passport/login?utm_source=workbuddy", HANDOFF)


if __name__ == "__main__":
    unittest.main(verbosity=2)
