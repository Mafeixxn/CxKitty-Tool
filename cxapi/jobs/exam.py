import difflib
import json
import re
import time

import requests
from bs4 import BeautifulSoup
from rich.json import JSON
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table

from logger import Logger
from searcher import SearcherBase, SearchResp

from ..schema import AccountInfo, QuestionModel, QuestionType

# 接口-单元测验答题提交
API_EXAM_COMMIT = "https://mooc1-api.chaoxing.com/work/addStudentWorkNew"

# SSR页面-客户端章节任务卡片
PAGE_MOBILE_CHAPTER_CARD = "https://mooc1-api.chaoxing.com/knowledge/cards"

# SSR页面-客户端单元测验答题页
PAGE_MOBILE_EXAM = "https://mooc1-api.chaoxing.com/android/mworkspecial"

# SSR页面-回顾已批阅试题 (网页端查看解析, 多个备选)
PAGE_REVIEW_EXAM_URLS = [
    # 1. doHomeWork (成功案例中服务端重定向的目标)
    "https://mooc1-api.chaoxing.com/mooc-ans/work/phone/doHomeWork",
    # 2. studentView 端点
    "https://mooc1-api.chaoxing.com/mooc-ans/work/studentView",
    "https://mooc1.chaoxing.com/mooc-ans/work/studentView",
    "https://mooc1.chaoxing.com/work/studentView",
]

# 搜索器槽位
searcher_slot: list[SearcherBase] = []


def add_searcher(searcher: SearcherBase):
    "添加搜索器"
    searcher_slot.append(searcher)


def remove_searcher(searcher: SearcherBase):
    "移除搜索器"
    searcher_slot.remove(searcher)


def invoke_searcher(question: str) -> list[SearchResp]:
    "调用搜索器"
    result = []
    if searcher_slot:
        for searcher in searcher_slot:
            result.append(searcher.invoke(question))
        return result
    raise NotImplementedError("至少需要加载一个搜索器")


def parse_question(question_node: BeautifulSoup, fallback_qid: int = 0):
    "解析题目 (兼容答题页和回顾页)"
    # 获取题目 id 和类型 (回顾页没有 answertype input)
    type_input = question_node.select_one("input[id*='answertype']")
    if type_input is not None:
        question_id = int(type_input["id"][10:])
        question_type = QuestionType(int(type_input["value"]))
    else:
        # 回顾页: 从题目标题文本推断类型
        question_id = fallback_qid
        title_div = question_node.find("div", {"class": "Py-m1-title"})
        title_text = title_div.get_text() if title_div else ""
        if "多选题" in title_text:
            question_type = QuestionType.多选题
        elif "判断题" in title_text:
            question_type = QuestionType.判断题
        elif "填空题" in title_text:
            question_type = QuestionType.填空题
        else:
            # 默认单选题 (回顾页最常见的题型)
            question_type = QuestionType.单选题

    # 查找并净化题目字符串
    q_title_node = question_node.find("div", {"class": "Py-m1-title"})
    if q_title_node is None:
        raise ValueError(f"题目 (id={question_id}) 未找到标题节点")
    value = "".join(list(q_title_node.strings)[2:]).strip().replace("\n", "").replace("\r", "")

    # 开始解析选项
    answer_map = {}
    if question_type in (QuestionType.单选题, QuestionType.多选题):
        answer_list = question_node.find("ul", {"class": "answerList"})
        if answer_list is None:
            answer_list = question_node.find("ul")
        if answer_list is not None:
            answers = answer_list.find_all("li")
            for answer in answers:
                k = ""
                option_text = ""
                # 方式1: 从 em 标签提取 (答题页 / 部分回顾页)
                if answer.em:
                    k = answer.em.get("id-param", "").strip()
                    if not k:
                        em_text = answer.em.get_text(strip=True)
                        k = em_text.rstrip(".").strip()
                    option_tags = answer.find_all(["p", "cc"])
                    if option_tags:
                        option_text = option_tags[-1].text.strip()
                # 方式2: 回顾页结构 <li><div>A.<p>文字</p></div></li>
                div = answer.find("div")
                if not k and div:
                    div_text = div.get_text(" ", strip=True)
                    m = re.match(r'([A-H])\.?\s*(.*)', div_text)
                    if m:
                        k = m.group(1)
                        option_text = m.group(2).strip()
                # 方式3: 直接从 li 文本提取
                if not k:
                    full_text = answer.get_text(" ", strip=True)
                    m = re.match(r'([A-H])\.?\s*(.*)', full_text)
                    if m:
                        k = m.group(1)
                        option_text = m.group(2).strip()
                if k:
                    answer_map[k] = option_text
    return QuestionModel(
        q_id=question_id, value=value, q_type=question_type, answers=answer_map, answer=""
    )


class ChapterExam:
    "章节测验"
    logger: Logger
    session: requests.Session
    acc: AccountInfo
    # 基本参数
    card_index: int  # 卡片索引位置
    point_index: int  # 任务点索引位置
    courseid: int
    knowledgeid: int
    cpi: int
    clazzid: int
    # 考试参数
    title: str
    workid: str
    jobid: str
    ktoken: str
    enc: str
    # 提交参数
    workAnswerId: int
    totalQuestionNum: str
    fullScore: str
    workRelationId: int
    enc_work: str
    # 答题参数
    questions: list[QuestionModel]
    # 施法参数
    need_jobid: bool

    def __init__(
        self,
        session: requests.Session,
        acc: AccountInfo,
        card_index: int,
        courseid: int,
        workid: str,
        jobid: str,
        knowledgeid: int,
        clazzid: int,
        cpi: int,
    ) -> None:
        self.session = session
        self.acc = acc
        self.card_index = card_index
        self.courseid = courseid
        self.workid = workid
        self.jobid = jobid
        self.knowledgeid = knowledgeid
        self.clazzid = clazzid
        self.cpi = cpi
        self.logger = Logger("PointExam")
        self.logger.set_loginfo(self.acc.phone)

    def pre_fetch(self) -> bool:
        "预拉取试题  返回是否需要完成"
        resp = self.session.get(
            PAGE_MOBILE_CHAPTER_CARD,
            params={
                "clazzid": self.clazzid,
                "courseid": self.courseid,
                "knowledgeid": self.knowledgeid,
                "num": self.card_index,
                "isPhone": 1,
                "control": "true",
                "cpi": self.cpi,
            },
        )
        resp.raise_for_status()
        html = BeautifulSoup(resp.text, "lxml")
        try:
            head_script = html.head.find("script", type="text/javascript") if html.head else None
            if head_script is None:
                raise ValueError("页面中未找到 script 标签")
            if r := re.search(
                r"window\.AttachmentSetting *= *(.+?);",
                head_script.text,
            ):
                attachment = json.loads(r.group(1))
            else:
                raise ValueError("未匹配到 AttachmentSetting")
            self.logger.debug(f"attachment: {attachment}")
            # 定位资源 workid
            for point in attachment["attachments"]:
                if prop := point.get("property"):
                    if prop.get("workid") == self.workid:
                        break
            else:
                self.logger.warning("定位任务资源失败")
                return False
            self.ktoken = attachment["defaults"]["ktoken"]
            self.enc = point["enc"]
            # 预存标题和 aid (用于回顾页)
            self.title = prop.get("title", "") if prop else ""
            self.aid = point.get("aid")
            # 检查 job 或 jobid 字段 (学习通 API 两种 key 都存在)
            if (job := point.get("job")) is not None or (job := point.get("jobid")) is not None:
                needtodo = job in (True, None)
                self.need_jobid = True
            else:
                self.need_jobid = False
                needtodo = True
            self.logger.info("预拉取成功")
        except Exception:
            self.logger.error("预拉取失败")
            raise RuntimeError("试题预拉取出错")
        return needtodo

    def fetch(self) -> bool:
        "拉取并解析试题 (先试答题页, 失败则试回顾页)"
        # 尝试答题页
        resp = self.session.get(
            PAGE_MOBILE_EXAM,
            params={
                "courseid": self.courseid,
                "workid": self.workid,
                "jobid": self.jobid if self.need_jobid else "",
                "needRedirect": "true",
                "knowledgeid": self.knowledgeid,
                "userid": self.acc.puid,
                "ut": "s",
                "clazzId": self.clazzid,
                "cpi": self.cpi,
                "ktoken": self.ktoken,
                "enc": self.enc,
            },
            allow_redirects=True,
        )
        resp.raise_for_status()
        self.logger.info(f"答题页 URL: {resp.url}")
        # 保存重定向后的页面 HTML
        orig_resp_text = resp.text
        try:
            from pathlib import Path
            dump_path = Path("output") / f"debug_page_{self.workid}.html"
            dump_path.parent.mkdir(exist_ok=True)
            dump_path.write_text(orig_resp_text, encoding="utf-8")
        except Exception:
            pass
        html = BeautifulSoup(orig_resp_text, "lxml")

        # 如果答题页返回无权限/已批阅, 尝试回顾页
        title_tag = html.find("title")
        need_review = False
        if title_tag:
            if re.search(r"已批阅", title_tag.text):
                need_review = True
        if html.find("p", {"class": "blankTips"}):
            need_review = True

        if need_review:
            self.logger.info("答题页不可用, 尝试回顾页...")
            review_html = None
            # 首先尝试原端点但去掉 enc/ktoken/jobid (回顾页不需要这些答题参数)
            try:
                resp2 = self.session.get(
                    PAGE_MOBILE_EXAM,
                    params={
                        "courseid": self.courseid,
                        "workid": self.workid,
                        "jobid": "",
                        "needRedirect": "true",
                        "knowledgeid": self.knowledgeid,
                        "userid": self.acc.puid,
                        "ut": "s",
                        "clazzId": self.clazzid,
                        "cpi": self.cpi,
                    },
                    allow_redirects=True,
                )
                resp2.raise_for_status()
                tmp = BeautifulSoup(resp2.text, "lxml")
                if tmp.find("div", {"class": "Py-mian1"}):
                    review_html = tmp
                    self.logger.info("原端点(无enc)回顾页拉取成功")
            except Exception as e:
                self.logger.debug(f"原端点(无enc)失败: {e}")

            if review_html is None:
                for review_url in PAGE_REVIEW_EXAM_URLS:
                    try:
                        resp = self.session.get(
                            review_url,
                            params={
                                "workId": self.workid,
                                "answerId": getattr(self, "aid", ""),
                                "classId": self.clazzid,
                                "courseId": self.courseid,
                                "cpi": self.cpi,
                                "ut": "s",
                                "knowledgeid": self.knowledgeid,
                            },
                            allow_redirects=True,
                        )
                        resp.raise_for_status()
                        temp_html = BeautifulSoup(resp.text, "lxml")
                        if temp_html.find("div", {"class": "Py-mian1"}):
                            review_html = temp_html
                            self.logger.info(f"回顾页拉取成功 (URL: {review_url})")
                            break
                        self.logger.debug(f"回顾页无题目节点 (URL: {review_url})")
                    except Exception as e:
                        self.logger.debug(f"回顾页 URL 尝试失败: {review_url} - {e}")
                        continue

            if review_html is not None:
                html = review_html
                # 保存回顾页 HTML 用于调试
                try:
                    from pathlib import Path
                    dump_path = Path("output") / "debug_reviewed.html"
                    dump_path.parent.mkdir(exist_ok=True)
                    dump_path.write_text(resp.text, encoding="utf-8")
                    self.logger.info(f"回顾页 HTML 已保存到 {dump_path}")
                except Exception:
                    pass
            else:
                self.logger.warning("所有回顾页 URL 均失败")

        # 检测页面类型
        title_tag = html.find("title")
        is_reviewed = (
            (title_tag and re.search(r"已批阅", title_tag.text) if title_tag else False)
            or bool(html.find("em", {"class": "right-answer"}))  # 回顾页有正确答案标记
            or "selectWorkQuestionYiPiYue" in resp.url  # 回顾页 URL
        )

        if p := html.find("p", {"class": "blankTips"}):
            if re.search(r"无效的权限", p.text):
                self.logger.warning(f"试题无权限 ({p.text.strip()})")
                return False

        h3_tag = html.find("h3", {"class": "py-Title"})
        if h3_tag is None:
            h3_tag = html.find("h3", {"class": "chapter-title"})
        if h3_tag is None:
            body_text = html.body.get_text()[:200] if html.body else "(无body)"
            self.logger.warning(f"试题页面结构异常: 未找到标题. 页面预览: {body_text}")
            try:
                from pathlib import Path
                dump_path = Path("output") / "debug_no_title.html"
                dump_path.parent.mkdir(exist_ok=True)
                dump_path.write_text(resp.text, encoding="utf-8")
                self.logger.warning(f"异常页面已保存到 {dump_path}")
            except Exception:
                pass
            return False
        self.title = h3_tag.text.strip()

        # 提取答题表单参数 (回顾页没有表单, 但题目结构相同)
        if not is_reviewed:
            try:
                self.workAnswerId = int(html.find("input", {"name": "workAnswerId"})["value"])
                self.enc_work = html.find("input", {"name": "enc_work"})["value"]
                self.totalQuestionNum = html.find("input", {"name": "totalQuestionNum"})["value"]
                self.fullScore = html.find("input", {"name": "fullScore"})["value"]
                self.workRelationId = int(html.find("input", {"name": "workRelationId"})["value"])
            except (TypeError, KeyError, ValueError) as e:
                self.logger.warning(f"试题表单参数解析失败: {e}")
                return False

        self.questions = []
        # 回顾页: 先收集所有正确答案 (存在 <em class="right-answer"> 中)
        right_answers = []
        if is_reviewed:
            for ra in html.find_all("em", {"class": "right-answer"}):
                i_tag = ra.find("i")
                if i_tag:
                    right_answers.append(i_tag.get_text(strip=True))

        for idx, question_node in enumerate(html.find_all("div", {"class": "Py-mian1"})):
            try:
                question = parse_question(question_node, fallback_qid=idx + 1)
                # 回顾页: 从 right_answers 中匹配正确答案
                if is_reviewed and idx < len(right_answers):
                    question.answer = right_answers[idx]
                self.questions.append(question)
                self.logger.debug(f"question schema: {question.__dict__}")
            except Exception as e:
                self.logger.warning(f"解析单道题目失败, 已跳过: {e}")

        page_type = "回顾页" if is_reviewed else "答题页"
        self.logger.info(
            f"试题[{page_type}]解析成功 共 {len(self.questions)} 道 [{self.title}(J.{self.jobid}/W.{self.workid})]"
        )
        return True

    @staticmethod
    def _find_correct_answer(question_node: BeautifulSoup, q_type: QuestionType) -> str:
        """从回顾页提取正确答案"""
        if q_type in (QuestionType.单选题, QuestionType.多选题):
            # 回顾页正确选项有 trueGreen 类 (绿色勾)
            answers = question_node.find_all("li", class_="trueGreen")
            if answers:
                keys = []
                for a in answers:
                    em = a.find("em")
                    if em and em.get("id-param"):
                        keys.append(em["id-param"].strip())
                keys.sort()
                return "".join(keys)
            # 也尝试找 checked 属性
            checked = question_node.find_all("input", checked=True)
            if checked:
                return ",".join(c.get("value", "") for c in checked)
        elif q_type == QuestionType.判断题:
            # 判断题: trueGreen 表示正确选项
            correct = question_node.find("li", class_="trueGreen")
            if correct:
                em = correct.find("em")
                if em and em.get("id-param"):
                    val = em["id-param"].strip()
                    return "true" if val in ("A", "对", "正确") else "false"
        elif q_type == QuestionType.填空题:
            # 填空题: 找正确答案填充
            blanks = question_node.find_all("input", {"name": re.compile(r"^answer")})
            if blanks:
                return ", ".join(b.get("value", "") for b in blanks)
            # 有些回顾页直接显示正确答案文本
            answer_spans = question_node.find_all("span", class_=re.compile(r"rightAnswer|correct"))
            if answer_spans:
                return "; ".join(s.get_text(strip=True) for s in answer_spans)
        return ""

    def __fill_answer(self, question: QuestionModel, search_results: list[SearchResp]) -> bool:
        "查询并填充对应选项"
        log_suffix = f"[{question.value}(Id.{question.q_id})]"
        self.logger.debug(f"开始填充题目 {log_suffix}")
        # 遍历多个搜索器返回以适配结果
        for result in search_results:
            if result.code != 0 or result.answer is None:
                continue
            search_answer = result.answer.strip()
            match question.q_type:
                case QuestionType.单选题:
                    for k, v in question.answers.items():
                        if difflib.SequenceMatcher(a=v, b=search_answer).ratio() >= 0.9:
                            question.answer = k
                            self.logger.debug(f"单选题命中 {k}={v} {log_suffix}")
                            return True
                    else:
                        self.logger.warning(f"单选题填充失败 {log_suffix}")
                        return False
                case QuestionType.判断题:
                    if re.search(r"(错|否|错误|false|×)", search_answer):
                        question.answer = "false"
                        self.logger.debug(f"判断题命中 true {log_suffix}")
                        return True
                    elif re.search(r"(对|是|正确|true|√)", search_answer):
                        question.answer = "true"
                        self.logger.debug(f"判断题命中 false {log_suffix}")
                        return True
                    else:
                        self.logger.warning(f"判断题填充失败 {log_suffix}")
                        return False
                case QuestionType.多选题:
                    option_lst = []
                    if len(part_answer_lst := search_answer.split("#")) <= 1:
                        part_answer_lst = search_answer.split(";")
                    for part_answer in part_answer_lst:
                        for k, v in question.answers.items():
                            if difflib.SequenceMatcher(a=v, b=part_answer).ratio() >= 0.9:
                                option_lst.append(k)
                                self.logger.debug(f"多选题命中 {k}={v} {log_suffix}")
                    # 多选题选项必须排序，否则提交错误
                    option_lst.sort()
                    if len(option_lst):
                        question.answer = "".join(option_lst)
                        self.logger.debug(f"多选题最终选项 {question.answer}")
                        return True
                    self.logger.warning(f"多选题填充失败 {log_suffix}")
                    return False
                case _:
                    self.logger.warning(
                        f"未实现的题目类型 {question.q_type.name}/{question.q_type.value} {log_suffix}"
                    )
                    return False
        else:
            self.logger.warning(f"题目匹配失败 {log_suffix}")
            return False

    def fill_and_commit(self, tui_ctx: Layout) -> None:
        "填充并提交试题 答题主逻辑"
        self.logger.info(f"开始完成试题 " f"[{self.title}(J.{self.jobid}/W.{self.workid})]")
        tb = Table("id", "类型", "题目", "选项")
        msg = Layout(name="msg")
        tui_ctx.split_column(tb, msg)
        tb.title = f"[bold yellow]答题中[/]  {self.title}"
        tb.border_style = "yellow"
        mistake_questions = []  # 答错题列表
        for question in self.questions:
            results = invoke_searcher(question.value)  # 调用搜索器搜索方法
            self.logger.debug(f"题库调用成功 req={question.value} rsp={results}")
            msg.update(
                Panel(
                    "\n".join(
                        (
                            f"[{'green' if result.code == 0 else 'red'}]"
                            f"{result.searcher.__class__.__name__} -> "
                            f"{'搜索成功' if result.code == 0 else f'搜索失败{result.code}:{result.message}'} -> "
                            f"{result.answer}[/]"
                        )
                        for result in results
                    ),
                    title="题库接口返回",
                )
            )
            # 填充选项
            status = self.__fill_answer(question, results)
            tb.add_row(
                str(question.q_id),
                question.q_type.name,
                question.value,
                (f"[green]{question.answer}" if status else "[red]未匹配"),
            )
            # 记录错题
            if status == False:
                mistake_questions.append(
                    (question, "/".join(str(result.answer) for result in results))
                )
            time.sleep(1.0)

        # 开始答题结束处理
        if (mistake_num := len(mistake_questions)) == 0:
            # 没有错误
            tb.title = f"[bold green]答题完毕[/]  {self.title}"
            tb.border_style = "green"
            # 提交试题
            commit_result = self.__commit()
            j = JSON.from_data(commit_result, ensure_ascii=False)
            if commit_result["status"] == True:
                self.logger.info(f"试题提交成功 " f"[{self.title}(J.{self.jobid}/W.{self.workid})]")
                msg.update(Panel(j, title="提交成功 TAT！", border_style="green"))
            else:
                self.logger.warning(f"试题提交失败 " f"[{self.title}(J.{self.jobid}/W.{self.workid})]")
                msg.update(Panel(j, title="提交失败！", border_style="red"))

        else:
            # 存在错误
            tb.title = f"[bold red]有{mistake_num}道错误[/]  {self.title}"
            tb.border_style = "red"
            msg.update(
                Panel(
                    "\n".join(f"q：{q.value}\na：{a}" for q, a in mistake_questions),
                    title="有错误的题",
                    highlight=False,
                    style="red",
                )
            )
            self.logger.warning(f"试题未完成 " f"[{self.title}(J.{self.jobid}/W.{self.workid})]")
            self.logger.warning(
                f"共 {mistake_num} 题未完成\n"
                + "--------------------\n"
                + "\n".join(
                    (
                        f"{i}.\tq({q.q_type.name}/{q.q_type.value}): {q.value} "
                        + (
                            f"\n\to: {' '.join(f'{k}={v}' for k, v in q.answers.items())}"
                            if q.q_type in (QuestionType.单选题, QuestionType.多选题)
                            else ""
                        )
                        + f"\n\ta: {a}"
                    )
                    for i, (q, a) in enumerate(mistake_questions, 1)
                )
                + "\n--------------------"
            )
            # TODO: 答题失败提交保存
        time.sleep(5.0)

    def __mk_answer_reqdata(self) -> dict[str, str]:
        "输出试题答案表单信息"
        result = {"answerwqbid": ",".join(str(q.q_id) for q in self.questions)}
        for q in self.questions:
            result[f"answer{q.q_id}"] = q.answer
            result[f"answertype{q.q_id}"] = q.q_type.value
        return result

    def __commit(self) -> dict:
        "提交答题信息"
        answer_data = self.__mk_answer_reqdata()
        self.logger.debug(f"试题提交 payload: {answer_data}")
        resp = self.session.post(
            API_EXAM_COMMIT,
            params={
                "keyboardDisplayRequiresUserAction": 1,
                "_classId": self.clazzid,
                "courseid": self.courseid,
                "token": self.enc_work,
                "workAnswerId": self.workAnswerId,
                "workid": self.workRelationId,
                "cpi:": self.cpi,
                "jobid": self.jobid,
                "knowledgeid": self.knowledgeid,
                "ua": "app",
            },
            data={
                "pyFlag": "",
                "courseId": self.courseid,
                "classId": self.clazzid,
                "api": 1,
                "mooc": 0,
                "workAnswerId": self.workAnswerId,
                "totalQuestionNum": self.totalQuestionNum,
                "fullScore": self.fullScore,
                "knowledgeid": self.knowledgeid,
                "oldSchoolId": "",
                "oldWorkId": self.workid,
                "jobid": self.jobid,
                "workRelationId": self.workRelationId,
                "enc_work": self.enc_work,
                "isphone": "true",
                "userId": self.acc.puid,
                "workTimesEnc": "",
                **answer_data,
            },
        )
        resp.raise_for_status()
        json_content = resp.json()
        self.logger.debug(f"试题提交 resp: {json_content}")
        return json_content


__all__ = ["ChapterExam"]
