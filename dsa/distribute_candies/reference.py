import random
import functools
import collections
import string
import math
import datetime

from typing import *
from functools import *
from collections import *
from itertools import *
from heapq import *
from bisect import *
from string import *
from operator import *
from math import *

inf = float('inf')


class Solution:
    def distributeCandies(self, candyType: List[int]) -> int:
        return min(len(candyType) >> 1, len(set(candyType)))


def distribute_candies(candyType):
    return Solution().distributeCandies(candyType)
