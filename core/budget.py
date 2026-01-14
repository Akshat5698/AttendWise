def bunk_budget(attended,total):
    count=0
    while True:
        total+=1
        if (attended/total)*100 >=75:
            count+=1
        else:
            break
    return count
