DXL_MINIMUM_POSITION_VALUE  = 0       
DXL_MAXIMUM_POSITION_VALUE  = 4095

min_angle = 0
max_angle = 360


def set_angle_conf(a_min, a_max, dxlamin, dxlamax):
    global DXL_MINIMUM_POSITION_VALUE, DXL_MAXIMUM_POSITION_VALUE, min_angle, max_angle

    DXL_MINIMUM_POSITION_VALUE  = dxlamin       
    DXL_MAXIMUM_POSITION_VALUE  = dxlamax

    min_angle = a_min
    max_angle = a_max

def map_value(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def dxl2degrees(dxl_value):
    return int(round(map_value(dxl_value, DXL_MINIMUM_POSITION_VALUE, DXL_MAXIMUM_POSITION_VALUE, min_angle, max_angle)))

def degrees2dxl(degree):
    return int(round(map_value(degree, min_angle, max_angle, DXL_MINIMUM_POSITION_VALUE, DXL_MAXIMUM_POSITION_VALUE)))

