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
    def singleNumber(self, nums: List[int]) -> int:
        return reduce(xor, nums)


def single_number(nums):
    return Solution().singleNumber(nums)
