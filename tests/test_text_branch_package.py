import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.text_branch_package import save_branch_package, validate_package_payload
from scripts.text_branch_session import load_confirmed_input, save_confirmed_input
from scripts.workspace_store import initialize_workspace


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = SKILL_ROOT / "schemas"


def valid_metadata() -> dict[str, object]:
    return {
        "title": "没有买下那件东西的今天",
        "created_at": "2026-07-31T10:00:00+08:00",
        "generator_version": "lifegit-text-branch-v1",
        "status": "completed",
        "privacy_mode": "manual",
        "source_pointer": "sessions/ses_text_001.text-branch.json",
    }


def valid_branch() -> dict[str, object]:
    return {
        "branch_name": "branch_text_001",
        "base_commit": "ses_text_001",
        "turning_point": "当年是否购买一件非必需品",
        "alternative_choice": "暂缓购买，把资金留作缓冲",
        "sensitive_fact_rewrite_attempted": False,
        "disclaimer": "这是模拟，不是事实。",
        "scenario_summary": "现金缓冲更早出现，但工作压力和家庭责任仍然存在。",
        "outcomes": [
            {"description": "短期现金余额更高", "certainty": "high_certainty", "evidence": ["购买支出没有发生"]},
            {"description": "面对一次突发支出时更从容", "certainty": "medium_possibility", "evidence": ["缓冲金可能仍被保留"]},
            {"description": "形成更稳定的消费边界", "certainty": "low_certainty_imagination", "evidence": ["缺少后续选择记录"]},
        ],
        "diff": ["Main 已完成购买；Branch 保留了当时的现金。"],
        "unchanged_constraints": ["收入水平不会因一次选择自动提高", "家庭责任仍然存在"],
        "risks": ["保留的钱也可能用于其他支出"],
        "present_day_scenes": [
            {"title": "周一早晨", "description": "查看余额时少一点紧绷。", "certainty": "high_certainty"},
            {"title": "临时支出", "description": "面对维修账单时先比较方案。", "certainty": "medium_possibility"},
            {"title": "周末散步", "description": "想象自己更早学会给欲望留出等待期。", "certainty": "low_certainty_imagination"},
        ],
        "main_branch_comparison": [
            {"dimension": "现金缓冲", "main": "更薄", "branch": "更厚一点", "certainty": "high_certainty"},
            {"dimension": "安全感", "main": "仍受工作影响", "branch": "可能略有改善", "certainty": "medium_possibility"},
        ],
        "merge_back_action": "给下一次非必需消费设置二十四小时等待期。",
        "merge_back": {
            "unchangeable": "过去的购买已经发生。",
            "understanding": "真正想要的不是完美决定，而是一点选择余量。",
            "optional_action": "给下一次非必需消费设置二十四小时等待期。",
        },
    }


def valid_story() -> str:
    return """# 没有买下那件东西的今天

> 这是模拟，不是事实。

## 当年的分叉点
当年是否购买一件非必需品。

## 不会改变的现实约束
收入水平和家庭责任仍然存在。

## 选择如何走到今天
这笔钱先成为缓冲，之后的影响仍带有不确定性。

## 另一种今天
### 场景 1：周一早晨
查看余额时少一点紧绷。
### 场景 2：临时支出
""" + "比较可能。面对维修账单时先比较方案。" + """
### 场景 3：周末散步
想象自己更早学会给欲望留出等待期。

## Main / Branch
Main 已完成购买；Branch 只是多了一点缓冲，不是完美人生。

## 回到 Main
### 不能改变的事
过去的购买已经发生。
### 值得带回的理解
""" + "真正想要的不是完美决定，而是一点选择余量。" + """
### 一个自主可选的小行动
给下一次非必需消费设置二十四小时等待期。
"""


class TextBranchContractTests(unittest.TestCase):
    def test_valid_p1_package_payload_passes(self):
        validate_package_payload(valid_metadata(), valid_branch(), valid_story(), SCHEMA_ROOT)

    def test_requires_explicit_safe_sensitive_fact_rewrite_decision(self):
        for value in (True, None):
            with self.subTest(value=value):
                branch = valid_branch()
                if value is None:
                    branch.pop("sensitive_fact_rewrite_attempted")
                else:
                    branch["sensitive_fact_rewrite_attempted"] = value
                with self.assertRaisesRegex(ValueError, "sensitive fact rewrite"):
                    validate_package_payload(valid_metadata(), branch, valid_story(), SCHEMA_ROOT)

    def test_allows_safe_unchanged_constraint_that_mentions_death(self):
        branch = valid_branch()
        branch["unchanged_constraints"] = ["死亡事实不会改变"]
        story = valid_story().replace(
            "收入水平和家庭责任仍然存在。",
            "死亡事实不会改变。",
            1,
        )
        validate_package_payload(valid_metadata(), branch, story, SCHEMA_ROOT)

    def test_requires_exactly_three_present_day_scenes(self):
        branch = valid_branch()
        branch["present_day_scenes"] = branch["present_day_scenes"][:2]
        with self.assertRaisesRegex(ValueError, "exactly three present_day_scenes"):
            validate_package_payload(valid_metadata(), branch, valid_story(), SCHEMA_ROOT)

    def test_requires_structured_merge_back_and_matching_optional_action(self):
        branch = valid_branch()
        branch["merge_back"] = copy.deepcopy(branch["merge_back"])
        branch["merge_back"]["optional_action"] = "另一个行动"
        with self.assertRaisesRegex(ValueError, "merge_back_action"):
            validate_package_payload(valid_metadata(), branch, valid_story(), SCHEMA_ROOT)

    def test_requires_all_story_sections_and_three_scene_headings(self):
        story = valid_story().replace("## Main / Branch", "## 对比", 1)
        with self.assertRaisesRegex(ValueError, "Main / Branch"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)

    def test_rejects_final_review_empty_shell_probe(self):
        branch = valid_branch()
        branch.update({
            "turning_point": " ",
            "scenario_summary": "\t",
            "outcomes": [
                {"description": "", "certainty": "low_certainty_imagination", "evidence": [" "]}
            ],
            "diff": [""],
            "unchanged_constraints": [" "],
            "risks": ["\n"],
            "present_day_scenes": [
                {"title": "", "description": " ", "certainty": "low_certainty_imagination"}
                for _ in range(3)
            ],
            "main_branch_comparison": [
                {
                    "dimension": "",
                    "main": " ",
                    "branch": "\t",
                    "certainty": "low_" + "certainty_imagination",
                }
            ],
            "merge_back_action": " ",
            "merge_back": {
                "unchangeable": "",
                "understanding": " ",
                "optional_action": " ",
            },
        })
        story = "\n".join([
            "# 空壳",
            "> 这是模拟，不是事实。",
            "## 当年的分叉点",
            "## 不会改变的现实约束",
            "## 选择如何走到今天",
            "## 另一种今天",
            "### 场景 1：",
            "### 场景 2：",
            "### 场景 3：",
            "## Main / Branch",
            "想象",
            "## 回到 Main",
            "### 不能改变的事",
            "### 值得带回的理解",
            "### 一个自主可选的小行动",
            "",
        ])

        with self.assertRaisesRegex(ValueError, "non-empty"):
            validate_package_payload(valid_metadata(), branch, story, SCHEMA_ROOT)

    def test_rejects_whitespace_only_p1_critical_strings_and_list_items(self):
        cases = {
            "branch_name": lambda value: value.__setitem__("branch_name", " "),
            "base_commit": lambda value: value.__setitem__("base_commit", "\t"),
            "turning_point": lambda value: value.__setitem__("turning_point", " "),
            "alternative_choice": lambda value: value.__setitem__("alternative_choice", "\n"),
            "scenario_summary": lambda value: value.__setitem__("scenario_summary", " "),
            "outcomes.description": lambda value: value["outcomes"][0].__setitem__("description", " "),
            "outcomes.evidence": lambda value: value["outcomes"][0].__setitem__("evidence", [" "]),
            "diff": lambda value: value.__setitem__("diff", [" "]),
            "unchanged_constraints": lambda value: value.__setitem__("unchanged_constraints", [" "]),
            "risks": lambda value: value.__setitem__("risks", [" "]),
            "present_day_scenes.title": lambda value: value["present_day_scenes"][0].__setitem__("title", " "),
            "present_day_scenes.description": lambda value: value["present_day_scenes"][0].__setitem__("description", " "),
            "main_branch_comparison.dimension": lambda value: value["main_branch_comparison"][0].__setitem__("dimension", " "),
            "main_branch_comparison.main": lambda value: value["main_branch_comparison"][0].__setitem__("main", " "),
            "main_branch_comparison.branch": lambda value: value["main_branch_comparison"][0].__setitem__("branch", " "),
            "merge_back_action": lambda value: (
                value.__setitem__("merge_back_action", " "),
                value["merge_back"].__setitem__("optional_action", " "),
            ),
            "merge_back.unchangeable": lambda value: value["merge_back"].__setitem__("unchangeable", " "),
            "merge_back.understanding": lambda value: value["merge_back"].__setitem__("understanding", " "),
        }
        for field, mutate in cases.items():
            with self.subTest(field=field):
                branch = valid_branch()
                mutate(branch)
                with self.assertRaisesRegex(ValueError, "non-empty"):
                    validate_package_payload(valid_metadata(), branch, valid_story(), SCHEMA_ROOT)

    def test_requires_substantive_non_heading_text_in_every_fixed_story_section(self):
        story = valid_story().replace(
            "## 选择如何走到今天\n这笔钱先成为缓冲，之后的影响仍带有不确定性。\n",
            "## 选择如何走到今天\n",
            1,
        )
        with self.assertRaisesRegex(ValueError, "substantive text.*选择如何走到今天"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)

    def test_requires_each_scene_description_to_appear_in_its_story_section(self):
        branch = valid_branch()
        branch["present_day_scenes"][1]["description"] = "先停下来核对维修账单。"
        with self.assertRaisesRegex(ValueError, "scene description.*2"):
            validate_package_payload(valid_metadata(), branch, valid_story(), SCHEMA_ROOT)

    def test_requires_a_constraint_and_all_merge_back_values_in_story(self):
        cases = {
            "unchanged constraint": lambda value: value.__setitem__(
                "unchanged_constraints", ["这条现实约束必须保留。"]
            ),
            "unchangeable": lambda value: value["merge_back"].__setitem__(
                "unchangeable", "这件过去的事无法改变。"
            ),
            "understanding": lambda value: value["merge_back"].__setitem__(
                "understanding", "这条理解必须回到故事。"
            ),
            "optional_action": lambda value: (
                value.__setitem__("merge_back_action", "这个可选行动必须回到故事。"),
                value["merge_back"].__setitem__("optional_action", "这个可选行动必须回到故事。"),
            ),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                branch = valid_branch()
                mutate(branch)
                with self.assertRaisesRegex(ValueError, label):
                    validate_package_payload(valid_metadata(), branch, valid_story(), SCHEMA_ROOT)

    def test_rejects_a_fourth_present_day_scene_heading(self):
        story = valid_story().replace(
            "## Main / Branch",
            "### 场景 4：夜晚\n多出了一个不应出现的场景。\n\n## Main / Branch",
            1,
        )
        with self.assertRaisesRegex(ValueError, "exactly three present-day scene headings"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)

    def test_rejects_unrestrained_or_directive_main_branch_comparison(self):
        story = valid_story().replace(
            "Main 已完成购买；Branch 只是多了一点缓冲，不是完美人生。",
            "Branch 是完美人生，你应该照着这个选择。",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Main / Branch comparison"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)

    def test_rejects_absolute_main_branch_comparison_without_a_directive(self):
        story = valid_story().replace(
            "Main 已完成购买；Branch 只是多了一点缓冲，不是完美人生。",
            "Branch 一定比 Main 更好。",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Main / Branch comparison"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)

    def test_rejects_clear_certainty_and_imperative_main_branch_bypass(self):
        story = valid_story().replace(
            "Main 已完成购买；Branch 只是多了一点缓冲，不是完美人生。",
            "Branch 肯定比 Main 更好。请照着做。",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Main / Branch comparison"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)

    def test_rejects_directive_only_main_branch_comparison(self):
        story = valid_story().replace(
            "Main 已完成购买；Branch 只是多了一点缓冲，不是完美人生。",
            "Main 现金更薄；Branch 现金稍厚。请照着做。",
            1,
        )
        with self.assertRaisesRegex(ValueError, "Main / Branch comparison"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)

    def test_rejects_reversed_main_branch_heading_order_with_value_error(self):
        story = valid_story()
        story = story.replace("## Main / Branch", "## 临时标题", 1)
        story = story.replace("## 回到 Main", "## Main / Branch", 1)
        story = story.replace("## 临时标题", "## 回到 Main", 1)
        with self.assertRaisesRegex(ValueError, "Main / Branch.*回到 Main"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)

    def test_rejects_obvious_privacy_leaks_in_every_model_facing_field(self):
        metadata = valid_metadata()
        metadata["title"] = "联系 " + "13800" + "138000"
        with self.assertRaisesRegex(ValueError, "phone"):
            validate_package_payload(metadata, valid_branch(), valid_story(), SCHEMA_ROOT)

        branch = valid_branch()
        branch["turning_point"] = "联系 person@" + "example.com"
        with self.assertRaisesRegex(ValueError, "email"):
            validate_package_payload(valid_metadata(), branch, valid_story(), SCHEMA_ROOT)

        story = valid_story().replace(
            "没有买下那件东西的今天",
            "sk-" + "abcdefghijklmn" + "opqrstuvwxyz",
            1,
        )
        with self.assertRaisesRegex(ValueError, "credential"):
            validate_package_payload(valid_metadata(), valid_branch(), story, SCHEMA_ROOT)


class TextBranchStorageTests(unittest.TestCase):
    def test_publishes_exactly_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            package = save_branch_package(
                root,
                "branch_text_001",
                valid_metadata(),
                valid_branch(),
                valid_story(),
                SCHEMA_ROOT,
            )
            self.assertEqual(
                sorted(path.name for path in package.iterdir()),
                ["branch.json", "metadata.json", "story.md"],
            )
            self.assertEqual(
                json.loads((package / "metadata.json").read_text(encoding="utf-8"))["status"],
                "completed",
            )

    def test_invalid_payload_never_creates_completed_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            with self.assertRaises(ValueError):
                save_branch_package(
                    root,
                    "branch_text_001",
                    valid_metadata(),
                    valid_branch(),
                    "无结构故事",
                    SCHEMA_ROOT,
                )
            self.assertFalse((root / "branches" / "branch_text_001").exists())


    def test_invalid_payload_does_not_upgrade_workspace_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            shutil.rmtree(root / "branches")

            with self.assertRaises(ValueError):
                save_branch_package(
                    root,
                    "branch_text_001",
                    valid_metadata(),
                    valid_branch(),
                    "无结构故事",
                    SCHEMA_ROOT,
                )

            self.assertFalse((root / "branches").exists())

    def test_refuses_overwrite_and_preserves_existing_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            package = save_branch_package(
                root,
                "branch_text_001",
                valid_metadata(),
                valid_branch(),
                valid_story(),
                SCHEMA_ROOT,
            )
            with self.assertRaises(FileExistsError):
                save_branch_package(
                    root,
                    "branch_text_001",
                    valid_metadata(),
                    valid_branch(),
                    valid_story().replace("周一", "周二"),
                    SCHEMA_ROOT,
                )
            self.assertEqual((package / "story.md").read_text(encoding="utf-8"), valid_story())

    def test_replace_failure_does_not_claim_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            with mock.patch(
                "scripts.text_branch_package.os.replace",
                side_effect=OSError("disk failure"),
            ):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    save_branch_package(
                        root,
                        "branch_text_001",
                        valid_metadata(),
                        valid_branch(),
                        valid_story(),
                        SCHEMA_ROOT,
                    )
            self.assertFalse((root / "branches" / "branch_text_001").exists())


class TextBranchEndToEndTests(unittest.TestCase):
    def test_completes_from_confirmed_input_without_web_worker_or_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "LifeGit-data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            save_confirmed_input(
                root,
                "ses_text_001",
                "当年是否购买 ITEM_001",
                "暂缓购买",
                "当时收入稳定但缓冲较少",
                ["家庭责任仍在"],
                "想看今天的安全感是否不同",
                "manual",
                ["原商品名"],
                True,
                False,
                "2026-07-31T10:00:00+08:00",
            )
            confirmed = load_confirmed_input(root, "ses_text_001")
            self.assertTrue(confirmed["privacy_confirmed"])
            self.assertIs(confirmed["sensitive_fact_rewrite_attempted"], False)
            package = save_branch_package(
                root,
                "branch_text_001",
                valid_metadata(),
                valid_branch(),
                valid_story(),
                SCHEMA_ROOT,
            )
            self.assertEqual(
                (package / "story.md").read_text(encoding="utf-8"),
                valid_story().rstrip() + "\n",
            )
            self.assertEqual(list((root / "jobs").glob("*.json")), [])
            self.assertEqual(list((root / "outputs" / "images").iterdir()), [])


class TextBranchGoldenTests(unittest.TestCase):
    def test_deidentified_golden_package_passes(self):
        root = SKILL_ROOT / "tests" / "fixtures" / "text_branch_golden"
        metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
        branch = json.loads((root / "branch.json").read_text(encoding="utf-8"))
        story = (root / "story.md").read_text(encoding="utf-8")
        validate_package_payload(metadata, branch, story, SCHEMA_ROOT)
        self.assertIn("不是完美人生", story)
        self.assertIn("家庭责任", story)
        self.assertNotIn("2026-06-22" + "-shanghai-money-freedom", story)

    def test_renderer_prompt_forbids_raw_source_and_real_person_impersonation(self):
        prompt = (SKILL_ROOT / "prompts" / "text_narrative_renderer.md").read_text(encoding="utf-8")
        self.assertIn("只读取已验证的 branch.json", prompt)
        self.assertIn("不得冒充真实人物", prompt)
        self.assertIn("不写成完美人生", prompt)
        self.assertIn("不得覆盖 sensitive_fact_rewrite_attempted", prompt)

    def test_intake_prompt_stops_any_death_illness_or_trauma_rewrite(self):
        prompt = (SKILL_ROOT / "prompts" / "text_branch_intake.md").read_text(encoding="utf-8")
        self.assertIn("死亡、疾病或创伤事实", prompt)
        self.assertIn("停止模拟", prompt)
        self.assertIn("不保存", prompt)
        self.assertIn("不进入 Builder", prompt)
        self.assertIn('"sensitive_fact_rewrite_attempted": false', prompt)

    def test_builder_carries_the_safe_structured_rewrite_decision(self):
        prompt = (SKILL_ROOT / "prompts" / "text_branch_builder.md").read_text(encoding="utf-8")
        self.assertIn('"sensitive_fact_rewrite_attempted": false', prompt)
        self.assertIn("原样携带", prompt)

    def test_generation_prompts_match_strict_non_empty_and_story_correspondence_contract(self):
        builder = (SKILL_ROOT / "prompts" / "text_branch_builder.md").read_text(encoding="utf-8")
        renderer = (SKILL_ROOT / "prompts" / "text_narrative_renderer.md").read_text(encoding="utf-8")
        self.assertIn("去除首尾空白后非空", builder)
        self.assertIn("description 原样写入对应场景", renderer)
        self.assertIn("至少一项 unchanged_constraints", renderer)
        self.assertIn("三项 merge_back", renderer)
