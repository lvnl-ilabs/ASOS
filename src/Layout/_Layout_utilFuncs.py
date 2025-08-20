# -*- coding: utf-8 -*-
#
# Copyright 2021 Malte von der Burg
# Copyright 2021 Jorick Kamphof
#
# SPDX-License-Identifier: Apache-2.0

"""
Provides utility functions for the Layout-class,
which shall be explicitely imported into the class in the file "Layout.py".

Contributors:
    - Malte von der Burg (@Malte)
    - Jorick Kamphof (@Jorick)
"""


## make sure that this file is never called on itself
assert __name__ != '__main__', 'these functions may only be imported into the class "Layout.py".'

## standard packages
import math


@staticmethod
def calc_euclidean_dist(p1_xy, p2_xy):
    """
    Calculate the Euclidean distance (=straight distance between two coordinates) with pythogaros theorem.
    NOTE: coordinates in SVG are currently downscaled to 1/6th. Thus, x6 necessary to return distance in [m].
    
    Parameters:
        - p1_xy: tuple. Has to contain (x,y)-coordinates
        - p2_xy: tuple. Has to contain (x,y)-coordinates
    
    Returns:
        - distance between points: float
    
    Contributors: @Jorick, @Malte
    """
    distance = math.sqrt((p1_xy[0] - p2_xy[0]) ** 2 + (p1_xy[1] - p2_xy[1]) ** 2)  # Pythagoras theorem
    distance *= 6  # account for scaling of coordinates in SVG-layout
    return distance


@staticmethod
def calc_heading_btw_coords(p1_xy, p2_xy, y_inverted=False):
    """
    Calculates the heading between two coordinates. Heading is returned as angle between [0°,360°).
    FROM: P1 TO: P2.
    
    Parameters:
        - p1_xy: tuple. Has to contain (x,y)-coordinates
        - p2_xy: tuple. Has to contain (x,y)-coordinates
        - y_inverted: bool, optional (default is False). Can be set to True to automatically account for an inverted y-axis (as in the SVG layout)  # added by @Malte
    
    Returns:
        - heading: float. In [°] within interval [0, 360)
    SOURCE: https://stackoverflow.com/questions/54873868/python-calculate-bearing-between-two-lat-long
    
    Contributors: @Jorick
    """
    x = p2_xy[0] - p1_xy[0]
    y = p2_xy[1] - p1_xy[1]
    if y_inverted:
        y = -y  # y-axis is inverted in SVG-layout
    heading = math.atan2(y, x)
    heading = math.degrees(heading) % 360  # the modulo-operator (%) maps the angle from 0° to 360° (no negative values if angle between 180° and 360°)
    return heading


@staticmethod
def convert_bearing_to_heading(bearing, heading_from_0to360=True):
    """
    Converts a bearing (angle in CW direction from true north) into a heading (angle defined in mathematical way).
    Conversion table:
        bearing --> heading
           0°   -->   90°
          90°   -->    0°
         180°   -->  270°
         270°   -->  180°
    
    Parameters:
        - bearing: float. Bearing in [°]
        - heading_from_0to360: bool, optional (default is True). If True, angle is in interval [0°,360°), else in interval (-180°, 180°].
    
                                                                                                                            Returns:
        - heading: float. Heading in [°]
    
    Contributors: @Malte
    """
    if heading_from_0to360:
        return (90 - bearing) % 360  # heading in interval [0° to 360°)
    else:
        return (-90 - bearing) % -360 + 180  # heading in interval (-180°,180°]


@staticmethod
def convert_heading_to_bearing(heading, round_to_decimals=None):
    """
    Converts a heading, i.e. angle defined in mathematical way, into a bearing, i.e. angle in CW direction from true north.
    Conversion table:
        heading --> bearing
           0°   -->   90°
          90°   -->    0°
         180°   -->  270°
         270°   -->  180°
    
    Parameters:
        - heading: float. Heading in [°]
        - round_to_decimals: int, default is None. If specified, function round(.) is used with ndigits=round_to_decimals
    
    Returns:
        - bearing: float. Bearing in [°]
    
    Contributors: @Malte
    """
    if round_to_decimals is None:
        return (90 - heading) % 360
    else:
        return round((90 - heading) % 360, round_to_decimals)
