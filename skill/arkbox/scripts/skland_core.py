#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""森空岛 / 鹰角通行证客户端核心模块。

零第三方依赖（纯 Python 标准库）。职责：
1. 登录：森空岛 App 扫码（推荐）/ 手机验证码
2. 凭证持久化：~/.arkbox/credentials.json（权限 600）
3. 森空岛 zonai API 签名（HMAC-SHA256 + MD5）
4. 明日方舟官网寻访记录 API（cate/history）
5. 森空岛玩家数据 API（binding / player info）

API 端点与签名算法来源：社区开源实现交叉验证
（ProbiusOfficial/Skland_API、FrostN0v0/nonebot-plugin-skland，2026-10 验证可用）。
"""

import gzip
import hashlib
import hmac
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

# Windows 终端默认编码（cp1252/GBK）无法输出 ⚠/✓ 等符号：统一强制 UTF-8 输出
for _stdio in (sys.stdout, sys.stderr):
    try:
        _stdio.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CRED_PATH = os.path.expanduser("~/.arkbox/credentials.json")

SKLAND_APP_CODE = "4ca99fa6b56cc2ba"   # 森空岛 App
WEB_APP_CODE = "be36d44aa36bfb5b"      # 明日方舟官网通行证

UA = "Skland/1.32.1 (com.hypergryph.skland; build:103201004; Android 33; ) Okhttp/4.11.0"
COMMON_HEADERS = {
    "User-Agent": UA,
    "Accept-Encoding": "gzip",
    "Connection": "close",
}

AS_BASE = "https://as.hypergryph.com"
ZONAI_BASE = "https://zonai.skland.com/api/v1"
AK_BASE = "https://ak.hypergryph.com"
BINDING_API = "https://binding-api-account-prod.hypergryph.com"


class ArkApiError(Exception):
    """业务/网络错误，message 面向用户可读。"""


# ---------------------------------------------------------------- HTTP 层

def http_json(url, method="GET", headers=None, body=None, cookies=None, timeout=20):
    """发起请求并解析 JSON 响应。返回 (status_code, payload_dict, set_cookies)。"""
    data = None
    hdrs = {**COMMON_HEADERS, **(headers or {})}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    if cookies:
        hdrs["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        resp = opener.open(req, timeout=timeout)
        raw = resp.read()
        status = resp.status
        set_cookies = {}
        for h, v in (resp.headers.items() if hasattr(resp.headers, "items") else []):
            if h.lower() == "set-cookie":
                pair = v.split(";", 1)[0]
                if "=" in pair:
                    k, val = pair.split("=", 1)
                    set_cookies[k.strip()] = val.strip()
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = e.code
        set_cookies = {}
        for h, v in e.headers.items():
            if h.lower() == "set-cookie":
                pair = v.split(";", 1)[0]
                if "=" in pair:
                    k, val = pair.split("=", 1)
                    set_cookies[k.strip()] = val.strip()
    except urllib.error.URLError as e:
        raise ArkApiError(f"网络请求失败: {e.reason}")
    except (TimeoutError, OSError) as e:
        # socket.timeout / ConnectionReset 等：统一转成人话错误，不让 CLI 裸 traceback
        raise ArkApiError(f"网络请求失败: {e}")

    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text), set_cookies
    except json.JSONDecodeError:
        return status, {"_raw": text[:500]}, set_cookies


def _raise_hg(payload, prefix):
    """鹰角通行证系（as.hypergryph.com）业务错误。"""
    status = payload.get("status")
    if status is not None and status != 0:
        raise ArkApiError(f"{prefix}: {payload.get('msg') or payload.get('message')}")


def _raise_zonai(payload, prefix):
    """森空岛 zonai 系业务错误。"""
    code = payload.get("code")
    if code is not None and code != 0:
        hint = ""
        if code == 10000:
            hint = "（cred 已失效，请重新登录）"
        raise ArkApiError(f"{prefix}: [{code}] {payload.get('message')}{hint}")


# ---------------------------------------------------------------- 登录

def login_send_phone_code(phone):
    _, payload, _ = http_json(
        f"{AS_BASE}/general/v1/send_phone_code", "POST",
        body={"phone": phone, "type": 2},
    )
    _raise_hg(payload, "发送验证码失败")


def login_by_phone_code(phone, code):
    _, payload, _ = http_json(
        f"{AS_BASE}/user/auth/v2/token_by_phone_code", "POST",
        body={"phone": phone, "code": code},
    )
    _raise_hg(payload, "验证码登录失败")
    return payload["data"]["token"]


def login_start_scan():
    """发起扫码登录，返回 scan_id。二维码内容为 hypergryph://scan_login?scanId=..."""
    _, payload, _ = http_json(
        f"{AS_BASE}/general/v1/gen_scan/login", "POST",
        body={"appCode": SKLAND_APP_CODE},
    )
    _raise_hg(payload, "获取登录二维码失败")
    return payload["data"]["scanId"]


def login_poll_scan(scan_id):
    """轮询一次扫码状态。返回 (state, token_or_None)。

    state: waiting（未扫）/ scanned（已扫待确认）/ confirmed（已确认，token 就绪）。
    接口约定：未扫码时返回非零 status + msg「未扫码」，属正常等待态而非错误。
    """
    status, payload, _ = http_json(
        f"{AS_BASE}/general/v1/scan_status?scanId={urllib.parse.quote(scan_id)}", "GET",
    )
    st = payload.get("status")
    msg = payload.get("msg") or payload.get("message") or ""
    if st != 0:
        if "未扫码" in msg:
            return "waiting", None
        if "过期" in msg or "失效" in msg:
            raise ArkApiError("二维码已过期，请重新运行 login 获取新码")
        raise ArkApiError(f"查询扫码状态失败: {msg}")
    scan_code = (payload.get("data") or {}).get("scanCode")
    if not scan_code:
        return "waiting", None
    # 已扫码：scanCode 换 token；未点确认时换取会失败 → scanned 继续等
    status2, p2, _ = http_json(
        f"{AS_BASE}/user/auth/v1/token_by_scan_code", "POST",
        body={"scanCode": scan_code},
    )
    if status2 == 200 and p2.get("status") == 0:
        return "confirmed", p2["data"]["token"]
    return "scanned", None


def grant_skland_code(hg_token):
    """鹰角 token → 森空岛 OAuth code。"""
    _, payload, _ = http_json(
        f"{AS_BASE}/user/oauth2/v2/grant", "POST",
        body={"appCode": SKLAND_APP_CODE, "token": hg_token, "type": 0},
    )
    _raise_hg(payload, "获取森空岛授权失败")
    return payload["data"]["code"]


def grant_web_token(hg_token):
    """鹰角 token → 官网通行证 token（type=1 直接返回 token）。"""
    _, payload, _ = http_json(
        f"{AS_BASE}/user/oauth2/v2/grant", "POST",
        body={"appCode": WEB_APP_CODE, "token": hg_token, "type": 1},
    )
    _raise_hg(payload, "获取官网通行证 token 失败")
    return payload["data"]["token"]


def skland_cred_by_code(grant_code):
    """森空岛 OAuth code → cred（含 cred 与 token，token 用于签名）。"""
    _, payload, _ = http_json(
        f"{ZONAI_BASE}/user/auth/generate_cred_by_code", "POST",
        body={"kind": 1, "code": grant_code},
    )
    _raise_zonai(payload, "获取 cred 失败")
    d = payload["data"]
    return {"cred": d["cred"], "token": d["token"]}


def skland_refresh_cred_token(cred):
    url = f"{ZONAI_BASE}/auth/refresh"
    status, payload, _ = http_json(url, "GET", headers={"cred": cred})
    if status == 200 and payload.get("status") == 0:
        return payload["data"]["token"]
    return None


# ---------------------------------------------------------------- 森空岛签名

def zonai_sign_headers(cred, cred_token, url, method, body=None):
    """构造 zonai.skland.com 带签名的请求头。

    算法（对照 nonebot-plugin-skland api/request.py）：
    secret = path + query(GET)/json_body(POST) + timestamp + sign_map_json
    sign   = md5( hex( hmac_sha256(cred_token, secret) ) )
    """
    ts = str(int(time.time()) - 1)
    sign_map = {"platform": "", "timestamp": ts, "dId": "", "vName": ""}
    parsed = urllib.parse.urlparse(url)
    if method.upper() == "POST":
        # 注意：参考实现的 body 序列化用 (", ", ": ") 分隔符，必须与实际发送一致
        query = json.dumps(body, ensure_ascii=False, separators=(", ", ": ")) if body is not None else ""
    else:
        query = parsed.query
    ca_str = json.dumps(sign_map, separators=(",", ":"))
    secret = f"{parsed.path}{query}{ts}{ca_str}"
    hex1 = hmac.new(cred_token.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256).hexdigest()
    sign = hashlib.md5(hex1.encode("utf-8")).hexdigest()
    return {
        **COMMON_HEADERS,
        "cred": cred,
        "sign": sign,
        "platform": "",
        "timestamp": ts,
        "dId": "",
        "vName": "",
    }


def zonai_get(cred, cred_token, path_with_query, prefix="请求失败"):
    url = f"{ZONAI_BASE}{path_with_query}"
    headers = zonai_sign_headers(cred, cred_token, url, "GET")
    _, payload, _ = http_json(url, "GET", headers=headers)
    _raise_zonai(payload, prefix)
    return payload["data"]


# ---------------------------------------------------------------- 官网寻访记录

def web_role_token(hg_token, uid):
    """官网通行证 token + 游戏 uid → role_token。"""
    _, payload, _ = http_json(
        f"{BINDING_API}/account/binding/v1/u8_token_by_uid", "POST",
        body={"uid": uid, "token": hg_token},
    )
    _raise_hg(payload, "获取 role_token 失败")
    return payload["data"]["token"]


def web_ak_cookie(role_token):
    """role_token → ak-user-center cookie。返回 (cookie, account_token)。"""
    url = f"{AK_BASE}/user/api/role/login"
    data = json.dumps({"token": role_token}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        **COMMON_HEADERS, "Content-Type": "application/json", "accept": "application/json",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=20)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(text)
            _raise_hg(payload, "获取官网 cookie 失败")
        except json.JSONDecodeError:
            pass
        raise ArkApiError(f"获取官网 cookie 失败: HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise ArkApiError(f"获取官网 cookie 失败: {reason}")
    raw = resp.read()
    if raw[:2] == b"\x1f\x8b":  # 请求头声明了 Accept-Encoding: gzip，需自行解压
        raw = gzip.decompress(raw)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ArkApiError(f"获取官网 cookie 失败：响应不是有效 JSON（{e}）")
    _raise_hg(payload, "获取官网 cookie 失败")
    cookie = None
    for h, v in resp.headers.items():
        if h.lower() == "set-cookie" and "ak-user-center=" in v:
            cookie = v.split("ak-user-center=", 1)[1].split(";", 1)[0]
    if not cookie:
        raise ArkApiError("获取官网 cookie 失败：响应中无 ak-user-center")
    return cookie


def gacha_headers(creds):
    """构造官网寻访记录接口请求头。

    X-Account-Token = 原始鹰角通行证 token（扫码/验证码所得）；
    X-Role-Token = role_token（官网 token 经 u8_token_by_uid 换发）。
    """
    return {
        **COMMON_HEADERS,
        "X-Account-Token": creds["hg_token"],
        "X-Role-Token": creds["role_token"],
        "Cookie": f"ak-user-center={creds['ak_cookie']}",
        "Referer": "https://ak.hypergryph.com/user",
    }


def gacha_categories(creds, uid):
    url = f"{AK_BASE}/user/api/inquiry/gacha/cate?uid={uid}"
    _, payload, _ = http_json(url, "GET", headers=gacha_headers(creds))
    _raise_hg(payload, "获取卡池目录失败")
    return payload.get("data") or []


def gacha_history_page(creds, uid, category, gacha_ts=None, pos=None, size=100):
    """拉一页寻访记录。返回 (list, has_more)。list 内每条为一抽。"""
    q = {"uid": uid, "category": category, "size": size}
    if gacha_ts is not None:
        q["gachaTs"] = gacha_ts
    if pos is not None:
        q["pos"] = pos
    url = f"{AK_BASE}/user/api/inquiry/gacha/history?{urllib.parse.urlencode(q)}"
    _, payload, _ = http_json(url, "GET", headers=gacha_headers(creds))
    _raise_hg(payload, "获取寻访记录失败")
    d = payload.get("data") or {}
    return d.get("list") or [], bool(d.get("hasMore"))


def gacha_history_all(creds, uid, category, progress=None, max_pages=100):
    """拉取某卡池目录的全量记录。

    返回 (records, truncated)。truncated=True 表示翻到 max_pages 仍有
    hasMore，记录可能不完整，调用方应标「已知缺口」，不要冒充全量。
    """
    out = []
    gacha_ts = pos = None
    truncated = False
    for page in range(max_pages):
        items, has_more = gacha_history_page(creds, uid, category, gacha_ts, pos)
        out.extend(items)
        if progress:
            progress(len(out), page + 1)
        if not has_more or not items:
            break
        gacha_ts = items[-1]["gachaTs"]
        pos = items[-1]["pos"]
        time.sleep(0.3)  # 温和限速
    else:
        truncated = True
    out.sort(key=lambda r: (int(r["gachaTs"]), r.get("pos") or 0))
    return out, truncated


# ---------------------------------------------------------------- 玩家数据

def player_binding(cred, cred_token):
    """获取绑定角色列表。返回明日方舟条目 [{uid, channelMasterId, nickName...}]。"""
    data = zonai_get(cred, cred_token, "/game/player/binding", "获取绑定角色失败")
    result = []
    for app in data.get("list", []):
        if app.get("appCode") != "arknights":
            continue
        for b in app.get("bindingList", []):
            result.append({
                "uid": b.get("uid"),
                "channelMasterId": b.get("channelMasterId"),
                "nickName": b.get("nickName"),
                "isOfficial": b.get("isOfficial"),
                "channelName": app.get("channelName"),
            })
    return result


def player_info(cred, cred_token, uid):
    """获取玩家信息（含干员持有 data.chars、skins 等）。"""
    return zonai_get(cred, cred_token, f"/game/player/info?uid={uid}", "获取玩家数据失败")




def refresh_credentials(creds, uid=None):
    """用已保存的 hg_token 静默换一套新凭证；失败才需要重新扫码。"""
    hg = creds.get("hg_token")
    if not hg:
        raise ArkApiError("凭证缺少 hg_token，请重新运行 login")
    try:
        skland = skland_cred_by_code(grant_skland_code(hg))
        web_token = grant_web_token(hg)
        bindings = player_binding(skland["cred"], skland["token"])
    except ArkApiError as e:
        raise ArkApiError(f"自动续期失败，需要重新登录：{e}")
    if not bindings:
        raise ArkApiError("自动续期失败：该账号未绑定明日方舟角色")
    target = uid or creds.get("uid")
    binding = next((b for b in bindings if str(b.get("uid")) == str(target)), bindings[0])
    role_token = web_role_token(web_token, binding["uid"])
    ak_cookie = web_ak_cookie(role_token)
    updated = {
        **creds,
        "hg_token": hg,
        "cred": skland["cred"],
        "cred_token": skland["token"],
        "web_token": web_token,
        "role_token": role_token,
        "ak_cookie": ak_cookie,
        "uid": binding["uid"],
        "nick_name": binding.get("nickName") or creds.get("nick_name"),
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_creds(updated)
    return updated


def ensure_auth(creds, uid=None):
    """轻量健康检查；cred 失效时用 hg_token 自动续期一次。"""
    try:
        player_binding(creds["cred"], creds["cred_token"])
        return creds
    except ArkApiError as e:
        if "[10000]" not in str(e):
            raise
        return refresh_credentials(creds, uid=uid)


# ---------------------------------------------------------------- 凭证持久化

def save_creds(creds):
    os.makedirs(os.path.dirname(CRED_PATH), exist_ok=True)
    fd = os.open(CRED_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(creds, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(CRED_PATH, 0o600)
    except OSError:
        pass


def load_creds(required=True):
    if not os.path.exists(CRED_PATH):
        if required:
            raise ArkApiError(
                f"未找到凭证文件 {CRED_PATH}。请先运行登录："
                f"python3 scripts/skland_core.py login"
            )
        return None
    with open(CRED_PATH, encoding="utf-8") as f:
        return json.load(f)


def creds_brief(creds):
    """给对话展示的安全摘要（不泄露完整凭证）。"""
    if not creds:
        return "（无凭证）"
    nick = creds.get("nick_name") or "?"
    uid = creds.get("uid") or "?"
    ts = creds.get("saved_at", "?")
    return f"昵称 {nick} | UID {uid} | 保存于 {ts}"


def mask_uid(uid, mode="mask"):
    """本地诊断（whoami/doctor）用的 UID 遮挡展示；分享产物一律不展示 UID。"""
    uid = str(uid or "")
    if len(uid) <= 2:
        return "***"
    if len(uid) <= 5:
        return uid[:1] + "***" + uid[-1:]
    return uid[:3] + "****" + uid[-2:]


def cmd_logout(args):
    """删除本地凭证文件（账号钥匙一并清除）。"""
    if not os.path.exists(CRED_PATH):
        print(f"未找到凭证文件 {CRED_PATH}，无需登出。")
        return
    os.remove(CRED_PATH)
    print(f"已删除本地凭证：{CRED_PATH}")
    print("提示：这只是删除本地令牌；如需彻底解除授权，请在森空岛 App 的授权管理里移除。")


# ---------------------------------------------------------------- CLI：登录引导

def _qr_render(scan_id, out_path):
    """生成可扫码的二维码；有 qrcode 就出 PNG，没有就出本地 HTML。"""
    content = f"hypergryph://scan_login?scanId={scan_id}"
    try:
        import qrcode
        img = qrcode.make(content)
        img.save(out_path)
        return out_path
    except Exception:
        # 不把可选依赖变成登录阻断：用临时 HTML + 公开 QR 渲染服务兜底
        import urllib.parse
        html_path = os.path.splitext(out_path)[0] + ".html"
        src = ("https://api.qrserver.com/v1/create-qr-code/?size=360x360&data="
               + urllib.parse.quote(content, safe=""))
        html_page = f"""<!DOCTYPE html><html lang="zh"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ArkBox 登录二维码</title><body style="margin:0;background:#f4f4f1;font-family:-apple-system,'PingFang SC',sans-serif;text-align:center;padding:40px 20px">
<h2>用森空岛 App 扫码</h2><p>扫完后请在手机上点「确认登录」</p>
<img src="{src}" width="360" height="360" alt="登录二维码" style="border:1px solid #ddd;background:#fff">
<p style="color:#777;font-size:12px">二维码约 2 分钟有效；如果图片加载失败，请确认网络后重试。</p>
</body></html>"""
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_page)
        return html_path


def _try_print_qr(scan_id):
    """优先打开二维码图片/页面；终端只打印路径和状态提示。"""
    out = _qr_render(scan_id, os.path.expanduser("~/.arkbox/login_qr.png"))
    print(f"登录二维码已生成: {out}")
    try:
        webbrowser.open("file://" + os.path.abspath(out))
    except Exception:
        pass
    return True


def cmd_login(args):
    print("== 明日方舟工具箱 登录 ==")
    print("方式 1: 森空岛 App 扫码（推荐）")
    print("方式 2: 手机号 + 短信验证码")
    mode = input("请选择 [1/2]（回车默认 1）: ").strip() or "1"

    if mode == "1":
        scan_id = login_start_scan()
        print("\n请用【森空岛 App】扫码并在手机上确认（约 2 分钟内有效）：\n")
        _try_print_qr(scan_id)
        token = None
        deadline = time.time() + 120
        state = "waiting"
        while time.time() < deadline:
            state, token = login_poll_scan(scan_id)
            if state == "confirmed":
                break
            if state == "scanned":
                print("已扫码，请在手机上点击确认...")
            time.sleep(2)
        if state != "confirmed":
            raise ArkApiError("扫码超时或未确认，请重试")
    else:
        phone = input("手机号: ").strip()
        login_send_phone_code(phone)
        code = input("短信验证码: ").strip()
        token = login_by_phone_code(phone, code)

    finish_login(token)


def finish_login(token, default_role_idx=0):
    """扫码/验证码拿到 token 后的公共换证流程（非交互；多角色时取第一个官服）。"""
    print("登录成功，正在换取各接口凭证...")
    print("① 换取森空岛凭证（cred）...")
    skland = skland_cred_by_code(grant_skland_code(token))
    print("② 获取官网通行证 token...")
    web_token = grant_web_token(token)
    print("③ 拉取角色绑定列表...")
    bindings = player_binding(skland["cred"], skland["token"])
    if not bindings:
        raise ArkApiError("该账号未绑定明日方舟角色")
    if len(bindings) > 1:
        print(f"检测到 {len(bindings)} 个角色，自动选择第一个：")
        for i, b in enumerate(bindings):
            print(f"  [{'*' if i == default_role_idx else ' '}] {b['nickName']} (UID {b['uid']}, {b.get('channelName') or ''})")
        binding = bindings[default_role_idx]
    else:
        binding = bindings[0]
    uid = binding["uid"]
    print(f"④ 获取寻访查询凭证（角色 {binding.get('nickName')}）...")
    # 注意：u8_token_by_uid 要传 grant type=1 新发的官网通行证 token，不是原始扫码 token
    role_token = web_role_token(web_token, uid)
    ak_cookie = web_ak_cookie(role_token)

    creds = {
        "hg_token": token,
        "cred": skland["cred"],
        "cred_token": skland["token"],
        "web_token": web_token,
        "role_token": role_token,
        "ak_cookie": ak_cookie,
        "uid": uid,
        "nick_name": binding.get("nickName"),
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_creds(creds)
    print(f"\n凭证已保存到 {CRED_PATH}（权限 600）")
    print(f"当前账号: {creds_brief(creds)}")
    print("提示: 凭证等同账号钥匙，请勿分享此文件或截图输出内容。")


def cmd_login_scan(args):
    """非交互扫码登录：生成二维码图片 → 轮询 → 全自动换证。供 Agent 直接调用。"""
    qr_out = os.path.abspath(getattr(args, "qr_out", None) or "/tmp/ark_login_qr.png")
    scan_id = login_start_scan()
    qr_path = _qr_render(scan_id, qr_out)
    print(f"QR_SAVED: {qr_path}", flush=True)
    print("等待手机扫码确认（最长 115 秒）...", flush=True)
    token, state = None, "waiting"
    deadline = time.time() + 115
    while time.time() < deadline:
        state, token = login_poll_scan(scan_id)
        if state == "confirmed":
            break
        if state == "scanned":
            print("已扫码，请在手机上点【确认登录】...", flush=True)
        time.sleep(2)
    if state != "confirmed":
        print("TIMEOUT: 二维码超时或未确认，请重新发起")
        sys.exit(3)
    finish_login(token)


def cmd_whoami(args):
    creds = load_creds()
    print(creds_brief(creds))
    try:
        bindings = player_binding(creds["cred"], creds["cred_token"])
        for b in bindings:
            print(f"  绑定角色: {b['nickName']} (UID {b['uid']})")
        print("凭证状态: 有效")
    except ArkApiError as e:
        print(f"凭证状态: 失效（{e}）→ 请重新运行 login")


def main():
    if len(sys.argv) < 2:
        print("用法: skland_core.py <login|login-scan [qr_path]|whoami|logout>")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "login":
        cmd_login(None)
    elif cmd == "login-scan":
        class _A: qr_out = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_login_scan(_A())
    elif cmd == "whoami":
        cmd_whoami(None)
    elif cmd == "logout":
        cmd_logout(None)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except ArkApiError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(2)
