#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""明日方舟六星间隔理论分布与运气位置。

官方规则（2026-10 核验）：
- 六星基础出率 2%；
- 连续 50 抽未出六星后，第 51 抽起每抽 +2%；
- 第 99 抽必出（硬保底）；
- 出六星后计数重置。官方标准/中坚六星计数跨同类型池；本工具因无法证明
  历史完整，按池独立统计。
期望间隔约 34.59 抽。

口径（重要）：
- 「池内间隔均值」= 各池可见六星间隔总和 / 间隔段数；
  不含当前还没出货的垫抽。
- 「整体效率」= 总抽数 / 六星数；含当前垫抽，和间隔均值不是一回事。
- 「理论位置」= 在同样段数的理论样本中，平均间隔优于多少比例的样本。
  例：10 段均值 23.4 抽 → 只有约 4.7% 的 10 段样本更低，
  所以是「优于约 95.3% 的同段数样本」。
  这是理论模型，不是全服排名。

纯标准库。n<=25 用精确卷积；更大样本用正态近似并在结果里标注。
"""

import math

BASE_SIX = 0.02
RAMP_START = 51   # 第 51 抽开始递增（第 51 抽 4%）
RAMP_STEP = 0.02
HARD_PITY = 99

EXACT_LIMIT = 25


def next_six_rate(pity):
    """当前垫抽下，下一抽的六星概率（百分数）。"""
    pity = max(0, int(pity or 0))
    if pity >= HARD_PITY:
        return 100.0
    if pity < RAMP_START - 1:
        return BASE_SIX * 100
    return min(100.0, (BASE_SIX + RAMP_STEP * (pity - (RAMP_START - 2))) * 100)


def six_star_pmf():
    """单次六星间隔的精确概率质量函数（下标 1..99）。"""
    pmf = [0.0] * (HARD_PITY + 1)
    p_no = 1.0
    for k in range(1, HARD_PITY + 1):
        if k >= HARD_PITY:
            p = 1.0
        elif k >= RAMP_START:
            p = min(1.0, BASE_SIX + RAMP_STEP * (k - RAMP_START + 1))
        else:
            p = BASE_SIX
        pmf[k] = p_no * p
        p_no *= (1.0 - p)
    return pmf


_PMF = six_star_pmf()


def six_star_cdf(n):
    """前 n 抽内至少出一个六星的概率 P(X <= n)。"""
    n = max(0, min(int(n), HARD_PITY))
    return sum(_PMF[1:n + 1])


def single_gap_percentile(gap):
    """单个间隔在单段分布中的位置（P(X<=gap)），只用于明细，不作主指标。"""
    return round(six_star_cdf(gap) * 100, 1)


def expected_gap():
    """理论期望间隔（约 34.59 抽）。"""
    return sum(k * _PMF[k] for k in range(1, HARD_PITY + 1))


def variance_gap():
    mean = expected_gap()
    return sum((k - mean) ** 2 * _PMF[k] for k in range(1, HARD_PITY + 1))


_EXPECTED = expected_gap()
_VARIANCE = variance_gap()


def mean_gap_distribution(n):
    """n 段独立间隔之和的精确分布：{sum: probability}。"""
    dist = {0: 1.0}
    for _ in range(n):
        nxt = {}
        for s, ps in dist.items():
            for k in range(1, HARD_PITY + 1):
                p = _PMF[k]
                if p:
                    key = s + k
                    nxt[key] = nxt.get(key, 0.0) + ps * p
        dist = nxt
    return dist


def mean_gap_better_than(gaps):
    """池内间隔均值的理论位置。

    返回 dict：
      better_than: 0-100，越高越欧；含义是「优于约 X% 的同段数样本」
      method: exact / normal
      n / observed_mean / expected_gap
    """
    gaps = list(gaps or [])
    n = len(gaps)
    if n == 0:
        return {"better_than": None, "method": None, "n": 0,
                "observed_mean": None,
                "expected_gap": round(_EXPECTED, 1)}
    obs_sum = sum(gaps)
    obs_mean = obs_sum / n
    if n <= EXACT_LIMIT:
        dist = mean_gap_distribution(n)
        cdf = sum(p for s, p in dist.items() if s <= obs_sum)
        better = (1.0 - cdf) * 100
        method = "exact"
    else:
        mean = n * _EXPECTED
        sd = math.sqrt(n * _VARIANCE)
        z = (obs_sum - mean) / sd if sd else 0.0
        # P(sum > obs_sum) = P(mean > obs_mean)
        better = 0.5 * math.erfc(z / math.sqrt(2)) * 100
        method = "normal"
    return {
        "better_than": round(better, 1),
        "method": method,
        "n": n,
        "observed_mean": round(obs_mean, 1),
        "expected_gap": round(_EXPECTED, 1),
    }


def gap_report(gaps):
    """对一批池内可见六星间隔生成汇总。

    保留旧字段 avg_gap / best / worst / gaps；新增 count / sum /
    better_than / method / expected_gap。不再输出 avg_percentile（旧口径
    是“单段分位的平均”，不是“平均间隔的位置”，容易误导）。
    """
    gaps = list(gaps or [])
    if not gaps:
        return None
    pos = mean_gap_better_than(gaps)
    avg_gap = sum(gaps) / len(gaps)
    return {
        "gaps": gaps,
        "count": len(gaps),
        "sum": sum(gaps),
        "avg_gap": round(avg_gap, 1),
        "best": min(gaps),
        "worst": max(gaps),
        "expected_gap": pos["expected_gap"],
        "better_than": pos["better_than"],
        "method": pos["method"],
        "single_percentiles": [single_gap_percentile(g) for g in gaps],
    }


if __name__ == "__main__":
    # 自检：CDF 单调、99 抽必出、期望 34.59、实际样本 95.3%
    prev = 0.0
    for n in range(1, HARD_PITY + 1):
        c = six_star_cdf(n)
        assert c >= prev - 1e-12, f"CDF 不单调 @{n}"
        prev = c
    assert abs(six_star_cdf(HARD_PITY) - 1.0) < 1e-9, "99 抽应 100%"
    assert abs(six_star_cdf(50) - (1 - 0.98 ** 50)) < 1e-12
    assert 34.5 < expected_gap() < 34.7, expected_gap()
    mid = next(n for n in range(1, HARD_PITY + 1) if six_star_cdf(n) >= 0.5)
    sample = [18, 40, 17, 18, 58, 9, 60, 6, 1, 7]
    gr = gap_report(sample)
    assert gr["avg_gap"] == 23.4
    assert gr["sum"] == 234 and gr["count"] == 10
    assert 94.5 <= gr["better_than"] <= 96.0, gr["better_than"]
    print(f"✓ 模型自检通过：期望 {expected_gap():.4f} 抽、中位数 {mid} 抽、99 抽必出")
    print(f"  10 段样本均值 {gr['avg_gap']} 抽 → 优于约 {gr['better_than']}% 同段数样本"
          f"（{gr['method']}）")
    for g in (1, 10, 34, 50, 99):
        print(f"  {g:>2} 抽单段位置 {single_gap_percentile(g):>5}%")
