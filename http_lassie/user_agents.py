import os
import random

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
USER_AGENTS_PATH = os.path.join(THIS_DIR, "user_agents.tsv")


def load_user_agents(file_path):
    user_agents = []
    max_proportion = 0
    with open(file_path) as f:
        for line in f:
            proportion, user_agent = line.strip().split("\t")
            proportion = float(proportion)
            user_agent = user_agent.strip()
            if proportion > max_proportion:
                max_proportion = proportion
            user_agents.append((proportion, user_agent))
    return user_agents, max_proportion

USER_AGENTS, MAX_PROPORTION = load_user_agents(USER_AGENTS_PATH)


def random_user_agent():
    # Do stochastic acceptance for fast proportional selection.
    # See: http://jbn.github.io/fast_proportional_selection/
    n = len(USER_AGENTS)
    while True:
        i = int(n * random.random())
        proportion = USER_AGENTS[i][0]
        if random.random() < proportion / MAX_PROPORTION:
            return USER_AGENTS[i][1]

