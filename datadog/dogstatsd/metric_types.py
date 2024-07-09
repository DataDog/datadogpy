from enum import Enum

class MetricType(Enum):
    COUNT = 'c'
    GAUGE = 'g'
    SET = 's'