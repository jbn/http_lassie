import os
import random

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
USER_AGENTS_PATH = os.path.join(THIS_DIR, "user_agents.tsv")


def load_user_agents(file_path):
    """
    Load the user agents from a file.

    :param file_path: the user agents TSV file of `Weight\tAgent String`
    :return: a tuple of the user agents and the maximum weight found
    """
    # TODO: ADD MORE STRINGS
    user_agents, max_weight = [], 0
    with open(file_path) as f:
        for line in f:
            weight, user_agent = line.strip().split("\t")
            weight = float(weight)
            user_agent = user_agent.strip()
            if weight > max_weight:
                max_weight = weight
            user_agents.append((weight, user_agent))
    return user_agents, max_weight

USER_AGENTS, MAX_PROPORTION = load_user_agents(USER_AGENTS_PATH)


def random_user_agent():
    """
    :return: a user string sampled in proportion to its usage weight
    """
    # Do stochastic acceptance for fast proportional selection.
    # See: http://jbn.github.io/fast_proportional_selection/
    n = len(USER_AGENTS)
    while True:
        i = int(n * random.random())
        proportion = USER_AGENTS[i][0]
        if random.random() < proportion / MAX_PROPORTION:
            return USER_AGENTS[i][1]

