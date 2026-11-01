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
    def minPatches(self, nums: List[int], n: int) -> int:
        x = 1
        ans = i = 0
        while x <= n:
            if i < len(nums) and nums[i] <= x:
                x += nums[i]
                i += 1
            else:
                ans += 1
                x <<= 1
        return ans


def min_patches(nums, n):
    return Solution().minPatches(nums, n)
