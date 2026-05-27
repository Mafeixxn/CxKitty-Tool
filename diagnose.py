#!/usr/bin/env python3
"""诊断脚本 — 扫描课程所有章节卡片的 iframe module 类型"""
import os, sys, json, re, time, getpass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from cxapi.api import ChaoXingAPI
from cxapi import get_dc, calc_infenc

# 登录
api = ChaoXingAPI()
import utils
sessions = utils.sessions_load()

if sessions:
    print(f"找到已保存的会话 ({len(sessions)} 个), 自动加载第一个...")
    ck = utils.ck2dict(sessions[0].ck)
    api.ck_load(ck)
    if not api.accinfo():
        print("会话已失效, 请重新登录")
        sessions = []

if not sessions:
    choice = input("登录方式 [1=密码 2=二维码]: ").strip()
    if choice == "1":
        phone = input("手机号: ").strip()
        passwd = getpass.getpass("密码: ").strip()
        ok, resp = api.login_passwd(phone, passwd)
        if not ok:
            print(f"登录失败: {resp}")
            sys.exit(1)
    elif choice == "2":
        api.qr_get()
        url = api.qr_geturl()
        print(f"\n请在浏览器打开并扫码:\n{url}\n")
        print("等待扫描...")
        while True:
            status = api.login_qr()
            if status.get("status") == True:
                break
            if status.get("type") in ("1", "2"):
                print("二维码失效/错误")
                sys.exit(1)
            time.sleep(1.5)
    else:
        sys.exit(0)
    api.accinfo()
    utils.save_session(api.ck_dump(), api.acc)

print(f"登录成功: {api.acc.name}\n")

# 拉取课程
classes = api.fetch_classes()
print(f"共 {len(classes.classes)} 门课程:")
for i, c in enumerate(classes.classes):
    status = "已结课" if c.state else "进行中"
    print(f"  [{i}] {c.name} — {status}")

choice = input("\n选择课程序号: ").strip()
chap = classes.fetch_chapters_by_index(int(choice))

# 遍历所有章节
all_modules = {}
exam_list = []

for idx in range(len(chap.chapters)):
    ch = chap.chapters[idx]
    params = {
        "id": ch.chapter_id,
        "courseid": chap.courseid,
        "fields": "id,parentnodeid,indexorder,label,layer,name,begintime,createtime,lastmodifytime,status,jobUnfinishedCount,clickcount,openlock,card.fields(id,knowledgeid,title,knowledgeTitile,description,cardorder).contentcard(all)",
        "view": "json",
        "token": "4faa8662c59590c6f43ae9fe5b002b42",
        "_time": get_dc(),
    }
    resp = chap.session.get(
        "https://mooc1-api.chaoxing.com/gas/knowledge",
        params={**params, "inf_enc": calc_infenc(params)},
    )
    cards_data = resp.json()

    for data_item in cards_data.get("data", []):
        for card in data_item.get("card", {}).get("data", []):
            desc = card.get("description", "")
            if not desc:
                continue
            modules = re.findall(r'module="(\w+)"', desc)
            for m in modules:
                if m not in all_modules:
                    all_modules[m] = []
                all_modules[m].append({
                    "chapter": f"{ch.label} {ch.name}",
                    "title": card.get("title", ""),
                })

            if "work" in modules:
                has_jobid = bool(re.search(r'"jobid"\s*:\s*"', desc))
                exam_list.append({
                    "chapter": f"{ch.label} {ch.name}",
                    "title": card.get("title", ""),
                    "has_jobid": has_jobid,
                    "desc_snippet": desc[:300]
                })

    if idx % 20 == 0:
        print(f"  扫描进度: {idx+1}/{len(chap.chapters)}")

print(f"\n{'='*60}")
print(f"发现的所有 iframe module 类型:")
for m, items in sorted(all_modules.items()):
    print(f"  [{m}] x{len(items)}")

print(f"\n{'='*60}")
print(f"试题 (module='work') 共 {len(exam_list)} 个:")
submitted = [e for e in exam_list if e["has_jobid"]]
unsubmitted = [e for e in exam_list if not e["has_jobid"]]
print(f"  未提交: {len(unsubmitted)} 个")
print(f"  已提交(有jobid): {len(submitted)} 个")

if submitted:
    print(f"\n  已提交的试题列表:")
    for e in submitted:
        print(f"    [{e['chapter']}] {e['title']}")
        print(f"      {e['desc_snippet'][:200]}")

if not submitted:
    print("\n  没有发现已提交的试题! 可能原因:")
    print("  1. 该课程确实没有提交过的试题")
    print("  2. 已提交试题的 module 类型变了 (看上面的类型列表)")
