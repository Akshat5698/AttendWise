def forecast(attended, total, steps=15):
    data = {
        "attend_all": [],
        "strategic": [],
        "bunk_all": []
    }

    a1, t1 = attended, total
    a2, t2 = attended, total
    a3, t3 = attended, total

    for i in range(1, steps + 1):
        # Attend all
        a1 += 1
        t1 += 1
        data["attend_all"].append(round((a1 / t1) * 100, 2))

        # Strategic bunk (attend only if below 75)
        if (a2 / t2) * 100 < 75:
            a2 += 1
        t2 += 1
        data["strategic"].append(round((a2 / t2) * 100, 2))

        # Bunk all
        t3 += 1
        data["bunk_all"].append(round((a3 / t3) * 100, 2))

    return data
