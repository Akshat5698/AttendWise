import matplotlib.pyplot as plt

def attendance_graph(subjects,percents):
    plt.bar(subjects,percents)
    plt.axhline(75)
    plt.show()
