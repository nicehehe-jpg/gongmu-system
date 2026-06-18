#!/usr/bin/env python3
"""
매주 stxfood.com 울산테크노매곡 식단표를 크롤링하여
index.html의 MEAL_DATA와 MEAL_WEEK_IMAGES를 자동 업데이트합니다.
GitHub Actions에서 매주 월요일 오전 8시(KST)에 실행됩니다.
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

BASE_URL = "https://www.stxfood.com"
LIST_URL = f"{BASE_URL}/archives/menu/list"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
KST = pytz.timezone("Asia/Seoul")


def get_this_week_range():
    """이번 주 월요일~토요일 날짜 범위 반환"""
    now = datetime.now(KST)
    monday = now - timedelta(days=now.weekday())
    saturday = monday + timedelta(days=5)
    return monday.date(), saturday.date()


def fetch_meal_list():
    """울산테크노매곡 식단표 목록에서 최근 게시물 URL 추출"""
    r = requests.get(LIST_URL, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    links = soup.find_all("a", href=re.compile(r"/archives/menu/detail/"))
    results = []
    for a in links:
        title = a.get_text(strip=True)
        if "울산테크노매곡" in title:
            href = a["href"]
            full_url = BASE_URL + href if href.startswith("/") else href
            results.append({"title": title, "url": full_url})
    return results[:4]  # 최근 4개


def fetch_meal_detail(url):
    """상세 페이지에서 이미지 URL 추출"""
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    # 원본 이미지 URL (thumb 없는 것 우선)
    img_urls = re.findall(
        r"https://www\.stxfood\.com/_data/archives/[^\s'\"<>]+\.(?:png|jpg|jpeg)",
        r.text, re.IGNORECASE
    )
    orig_url = None
    thumb_url = None
    for u in set(img_urls):
        if "_thumb_" not in u:
            orig_url = u
        else:
            thumb_url = u

    return thumb_url or orig_url


def parse_week_label(title):
    """제목에서 주차 정보 파싱 (예: '6월 4주 식단표' → '6월 4주')"""
    m = re.search(r"(\d+월\s*\d+주)", title)
    return m.group(1).replace(" ", " ") if m else title


def build_week_dates(label):
    """주차 라벨로 날짜 범위 추정 (예: '6월 3주' → '16일~21일')"""
    now = datetime.now(KST)
    year = now.year
    m = re.search(r"(\d+)월\s*(\d+)주", label)
    if not m:
        return label
    month = int(m.group(1))
    week = int(m.group(2))
    # 해당 월의 첫 번째 월요일 계산
    first_day = datetime(year, month, 1, tzinfo=KST)
    first_monday = first_day + timedelta(days=(7 - first_day.weekday()) % 7)
    if first_monday.day > 7:
        first_monday = first_day
    start = first_monday + timedelta(weeks=week - 1)
    end = start + timedelta(days=5)
    return f"{month}월 {week}주 ({start.day}일~{end.day}일)"


def generate_meal_week_images_js(meal_list):
    """MEAL_WEEK_IMAGES JavaScript 배열 생성"""
    items = []
    for item in meal_list:
        img_url = fetch_meal_detail(item["url"])
        label = parse_week_label(item["title"])
        date_label = build_week_dates(label)
        if img_url:
            items.append({
                "label": date_label,
                "url": img_url,
                "detailUrl": item["url"]
            })
            print(f"  ✓ {date_label} → {img_url[:60]}...")

    lines = ["const MEAL_WEEK_IMAGES = ["]
    for it in items:
        lines.append("  {")
        lines.append(f"    label:'{it['label']}',")
        lines.append(f"    url:'{it['url']}',")
        lines.append(f"    detailUrl:'{it['detailUrl']}'")
        lines.append("  },")
    lines.append("];")
    return "\n".join(lines)


def update_index_html(new_images_js):
    """index.html의 MEAL_WEEK_IMAGES 블록을 새 데이터로 교체"""
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()

    # MEAL_WEEK_IMAGES 블록 교체
    pattern = r"const MEAL_WEEK_IMAGES = \[.*?\];"
    new_content = re.sub(pattern, new_images_js, content, flags=re.DOTALL)

    if new_content == content:
        print("⚠️  MEAL_WEEK_IMAGES 패턴을 찾지 못했습니다. 수동 확인 필요.")
        return False

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_content)

    print("✅ index.html 업데이트 완료")
    return True


def main():
    print(f"[{datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}] 식단표 자동 업데이트 시작")

    print("📋 stxfood.com 울산테크노매곡 식단표 목록 조회 중...")
    meal_list = fetch_meal_list()
    if not meal_list:
        print("❌ 식단표 목록을 가져오지 못했습니다.")
        return

    print(f"  → {len(meal_list)}개 게시물 발견")
    for item in meal_list:
        print(f"    - {item['title']}")

    print("\n🖼️  이미지 URL 수집 중...")
    new_images_js = generate_meal_week_images_js(meal_list)

    print("\n📝 index.html 업데이트 중...")
    update_index_html(new_images_js)

    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
