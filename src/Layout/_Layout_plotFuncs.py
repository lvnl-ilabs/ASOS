# -*- coding: utf-8 -*-
#
# Copyright 2021 Malte von der Burg
#
# SPDX-License-Identifier: Apache-2.0

"""
Provides plotting functions for the Layout-class,
which shall be explicitely imported into the class in the file "Layout.py".

Contributors:
    - Malte von der Burg (@Malte)
"""


## make sure that this file is never called on itself
assert __name__ != '__main__', 'these functions may only be imported into the class "SIMP.py".'

## standard packages
import math
import numpy as np
import matplotlib.pyplot as plt
from types import ModuleType


#%% Functions to define layout-styles
def define_default_layout_styles(self):
    """
    Contributors: @Malte
    """
    self.layout_styles = {}
    self.define_layout_style(name = 'default',
                             kwargs_edgeTypes_dict = {'default': {'c':'k'},
                                                      'RWY_edge': {'c':(0.6,0.6,0.6), 'lw':8, 'zorder':1.99},
                                                      'ServiceRoad': {'c':'tab:blue'},
                                                      'CenterServiceRoad': {'c':'tab:blue'}},
                             kwargs_nodeTypes_dict = {'default': {'marker':'o', 'ms':3, 'mfc':'k', 'mec':'k', 'mew':0.5, 'label':'node'},
                                                      'Ramp': {'marker':'o', 'ms':6, 'mfc':'lightgreen', 'mec':'k', 'mew':1, 'label':'Ramp'},
                                                      'Stopbar': {'marker':'8', 'ms':6, 'mfc':'tab:red', 'mec':'k', 'mew':1, 'label':'Stopbar'},
                                                      'SR_intersection': {'marker':'o', 'ms':3, 'mfc':'tab:blue', 'mec':'tab:blue', 'mew':0.5, 'label':'node'},
                                                      'Tug_Base': {'marker':'o', 'ms':6, 'mfc':'#0b85a5', 'mec':'tab:blue', 'mew':1, 'label':'Tug Base'},
                                                      'Decoupling_Point': {'marker':'o', 'ms':6, 'mfc':'tab:orange', 'mec':'k', 'mew':1, 'label':'Decoupling Point'},
                                                      'AllClear_Point': {'marker':'o', 'ms':6, 'mfc':'lightgrey', 'mec':'tab:blue', 'mew':1, 'label':'All-clear Point'},
                                                      'Termination_node': {'marker':'o', 'ms':3, 'mfc':'k', 'mec':'k', 'mew':0, 'label':'Termination node'},
                                                      'SegPts': None},  # do not plot segment-points of edges
                             kwargs_specials_dict = {'arrow_edge_direction': {'shape':'full', 'lw':None, 'c':'k', 'length_includes_head':False, 'head_width':1, 'head_length':1},
                                                     'text_on_edge': {'size':'x-small', 'va':'center', 'ha':'center'}})
    
    self.define_layout_style(name = 'default_background',
                             kwargs_edgeTypes_dict = {'default': {'c':'lightgrey'},
                                                      'RWY_edge': {'c':'darkgrey', 'lw':4, 'zorder':2.01}},
                             kwargs_nodeTypes_dict = {'default': {'marker':'o', 'ms':2, 'mfc':'lightgrey', 'mec':'lightgrey', 'mew':0}})
    
    self.define_layout_style(name = 'default_path',
                             kwargs_edgeTypes_dict = {'default': {'c':'tab:red', 'lw':3, 'zorder':2.02}},
                             kwargs_nodeTypes_dict = {'default': {'marker':'o', 'ms':4.5, 'mfc':'tab:olive', 'mec':'tab:red', 'mew':1, 'zorder':2.03, 'label':'path'}})


def define_layout_style(self, name, kwargs_edgeTypes_dict, kwargs_nodeTypes_dict, kwargs_specials_dict={}):
    """
    Defines a layout-style that can be called by the provided name.
    The style-definition is based on keyword-arguments (kwargs) for each edge-type and each node-type.
    Available edge-types are:
        - required: 'default'. This has to be provided, as it will be used when type is not specified
        - optional: 'TWY_edge', 'RWY_edge', 'Stand', 'ServiceRoad', 'CenterServiceRoad', 'PB/PUSH-PULL_placeholder', 'entry_placeholder'
    Available node-types are:
        - required: 'default'. This has to be provided, as it will be used when type is not specified
        - optional: 'TWY_intersection', 'RWY_intersection', 'Ramp', 'Stopbar', 'Decoupling_Point', 'AllClear_Point', 'Tug_Base', 'Termination_node'
        - specials: 'SegPts'
    Common abbreviations for kwargs of plt.plot:
        - c: color
        - marker
        - mec: markeredgecolor
        - mew: markeredgewidth
        - ms: markersize
        - label
        - zorder: regular z-order: patch/marker = 1, line = 2, text = 3
    
    Parameters:
        - name: str. Name of layout-style
        - kwargs_edgeTypes_dict
        - kwargs_nodeTypes_dict
    
    Returns: None
    
    Contributors: @Malte
    """
    assert 'default' in kwargs_edgeTypes_dict.keys(), 'kwargs-dict for edge-type "default" has to be specified.'
    for edgeType,kwargs_dict in kwargs_edgeTypes_dict.items():
        assert isinstance(kwargs_dict, dict) or kwargs_dict == None, 'kwargs-dict for edge-type "{}" has to be either a dict or None.'.format(edgeType)
    assert 'default' in kwargs_nodeTypes_dict.keys(), 'kwargs-dict for node-type "default" has to be specified.'
    for edgeType,kwargs_dict in kwargs_edgeTypes_dict.items():
        assert isinstance(kwargs_dict, dict) or kwargs_dict == None, 'kwargs-dict for edge-type "{}" has to be either a dict or None.'.format(edgeType)
    
    ## add kwargs-dicts to layout-style
    layout_style = {'kwargs_edgeTypes_dict':kwargs_edgeTypes_dict, 'kwargs_nodeTypes_dict':kwargs_nodeTypes_dict, 'kwargs_specials_dict':kwargs_specials_dict}
    self.layout_styles[name] = layout_style
    

def list_layout_styles(self):
    """
    Lists the names of all available layout-styles.
    
    Contributors: @Malte
    """
    ## define text to list available layout-styles
    text = ''
    for k,v in self.layout_styles.items():
        text += '\n - "{}" with kwarg-dicts:'.format(k)
        for vk,vv in v.items():
            if not vv:
                text += '\n\t - "{}" without sub-dicts'.format(vk)
            else:
                text += '\n\t - "{}" with sub-dicts:'.format(vk)
                for vvk in vv.keys():
                    text += '\n\t\t - "{}"'.format(vvk)
        text += '\n'
    ## print to console
    print('available layout styles are: {}'.format(text))



#%% Functions to plot layout
def plot_edge(self, edge_id, kwargs_edge, ax, intvl=(0,1), simplify=False):
    """
    Plots the line of an edge from self.edges_dict onto a given axis-object.
    
    Parameters:
        - edge_id: tuple. Edge-ID of edge from self.edges_dict
        - kwargs_edge: dict with kwargs for plotting the points. All kwargs from "plt.plot" can be used.
        - ax: axis-object to plot the segment-points of the edge into.
    
    Returns:
        - line: plt.plot-object for further use, e.g. for legends
    
    Contributors: @Malte
    """
    edge = self.edges_dict[edge_id]
    if intvl == (0,1):
        path = edge['path']
    else:
        path = edge['path'].cropped(*intvl)
    ## create array of points representing the edge
    line_pts = []
    for elem in path:
        line_pts.append(elem.start)
        if len(elem) != 2:
            num_samples = round(elem.length()*6)  # this will split the segment into number of samples equal to rounded length in [m]
            for i in range(1,num_samples):
                line_pts.append(elem.point(i/(num_samples)))
    line_pts.append(elem.end)
    if simplify:
        line_pts = [line_pts[0], line_pts[-1]]
    line_pts = np.array(line_pts)
    ## plot line (only when kwargs are not None)
    line, = ax.plot(line_pts.real, line_pts.imag, **kwargs_edge)  # ax.plot returns a list - the "," ensures that only the 1st object is taken, i.e., the line
    ## return line-object to e.g. add a legend for it
    return line


def highlight_edges(self, edge_ids, kwargs_edge={'c':'r', 'zorder':3}, plot_edgeDir=True, plt_or_ax=plt):
    """
    Highlights either a single or multiple edges in the layout.
    When not passing an axis explicitly, the entire layout is plotted with the layout-style "default_background".
    Then, given the edge-kwargs, the edges are plotted.
    
    Parameters:
        - edge_ids: tuple, list, or set. Either a single edge-ID as tuple, or multiple in a list or set.
        - kwargs_edge: dict with kwargs for plotting the points, optional. All kwargs from "plt.plot" can be used.
        - plt_or_ax: axis-object, optional (default is plt as abbreviation for matplotlib.pyplot). Can be either:
            - plt: matplotlib.pyplot. This will plot the layout into a created figure
            - ax: axis-object. This will plot the layout onto the given axis-object
    
    Returns: axis-object
    
    Contributors: @Malte
    """
    ### ----- figure initialization ----- ###
    if isinstance(plt_or_ax, ModuleType) and plt_or_ax == plt:
        self.plot_layout('default_background')
        fig = plt.gcf()
        ax = fig.gca()
        ax.set_title('Layout of Airport {}'.format(self.airport_id))
    else:
        ax = plt_or_ax
        fig = plt.gcf()
    
    ### ----- plot edges ----- ###
    if isinstance(edge_ids, tuple) and edge_ids in self.edges_dict.keys():
        edge_ids = [edge_ids]
    [self.plot_edge(edge_id, kwargs_edge, ax=ax) for edge_id in edge_ids]
    kwargs_arrow = {'shape':'full', 'lw':None, 'color':kwargs_edge['c'], 'length_includes_head':False, 'head_width':1, 'head_length':1}
    [self.plot_edge_direction(edge_id, kwargs_arrow, ax=ax) for edge_id in edge_ids]
    return ax


def plot_node(self, node_id, kwargs_node, ax):
    """
    Plots a node from self.nodes_dict onto a given axis-object.
    
    Parameters:
        - node_id: int or str. Node-ID of node from self.nodes_dict or its name from self.name2node_dict
        - kwargs_node: dict with kwargs for plotting the node. All kwargs from "plt.plot" can be used.
        - ax: axis-object to plot the node into.
    
    Returns: None
    
    Contributors: @Malte
    """
    ## convert node-name into node-ID if passed as such into input "node_id"
    if isinstance(node_id, str):
        node_id = self.name2node_dict[node_id]
    ## plot node (only when kwargs are not None)
    pos_xy = self.nodes_dict[node_id]['pos_xy']
    ax.plot(*pos_xy, **kwargs_node)


def highlight_nodes(self, node_ids, kwargs_node={'c':'r', 'marker':'.', 'zorder':3}, plt_or_ax=plt):
    """
    Highlights either a single or multiple edges in the layout.
    When not passing an axis explicitly, the entire layout is plotted with the layout-style "default_background".
    Then, given the edge-kwargs, the edges are plotted.
    
    Parameters:
        - edge_ids: tuple, list, or set. Either a single edge-ID as tuple, or multiple in a list or set.
        - kwargs_edge: dict with kwargs for plotting the nodes, optional. All kwargs from "plt.plot" can be used.
        - plt_or_ax: axis-object, optional (default is plt as abbreviation for matplotlib.pyplot). Can be either:
            - plt: matplotlib.pyplot. This will plot the layout into a created figure
            - ax: axis-object. This will plot the layout onto the given axis-object
    
    Returns: axis-object
    
    Contributors: @Malte
    """
    ### ----- figure initialization ----- ###
    if isinstance(plt_or_ax, ModuleType) and plt_or_ax == plt:
        self.plot_layout('default_background')
        fig = plt.gcf()
        ax = fig.gca()
        ax.set_title('Layout of Airport {}'.format(self.airport_id))
    else:
        ax = plt_or_ax
        fig = plt.gcf()
    
    ### ----- plot nodes ----- ###
    if isinstance(node_ids, int) and node_ids in self.nodes_dict.keys():
        node_ids = [node_ids]
    elif isinstance(node_ids, str) and node_ids in self.name2node_dict.keys():
        node_ids = [self.name2node_dict[node_ids]]
    [self.plot_node(node_id, kwargs_node, ax=ax) for node_id in node_ids]
    return ax


def plot_edge_segPts(self, edge_id, kwargs_segPts, ax):
    """
    Plots the points of all segments making up an edge from self.edges_dict onto a given axis-object.
    
    Parameters:
        - edge_id: tuple. Edge-ID of edge from self.edges_dict
        - kwargs_segPts: dict with kwargs for plotting the line. All kwargs from "plt.plot" can be used.
        - ax: axis-object to plot the line of the edge into.
    
    Returns: None
    
    Contributors: @Malte
    """
    edge = self.edges_dict[edge_id]
    ## create array of points representing the start- and end-points of all segments
    seg_pts = []
    for elem in edge['path']:
        seg_pts.append(elem.start)
    seg_pts.append(elem.end)
    seg_pts = np.array(seg_pts)
    ## plot points of edge segments
    ax.plot(seg_pts.real, seg_pts.imag, **kwargs_segPts)


def plot_edge_direction(self, edge_id, kwargs_arrow, ax):
    """
    Plots the directionality of an edge from self.edges_dict onto a given axis-object by using a plt.arrow-patch.
    The arrow is plotted in the middle of the edge.
    
    Parameters:
        - edge_id: tuple. Edge-ID of edge from self.edges_dict
        - kwargs_arrow: dict with kwargs for plotting the arrow. All kwargs from "plt.arrow" can be used.
        - ax: axis-object to plot the arrow for the edge direction into.
    
    Returns: None
    
    Contributors: @Malte
    """
    edge = self.edges_dict[edge_id]
    T = edge['path'].ilength(edge['path'].length() / 2)
    xy_mid = edge['path'].point(T)
    (x_mid, y_mid) = (xy_mid.real, xy_mid.imag)
    xy_mid2 = edge['path'].point(T + 1e-6)
    (dx, dy) = (xy_mid2.real - x_mid, xy_mid2.imag - y_mid)
    ax.arrow(x_mid, y_mid, dx, dy, **kwargs_arrow)


def plot_text_on_edge(self, edge_id, text, kwargs_text, ax):
    """
    Plots a text at the middle of an edge from self.edges_dict onto a given axis-object.
    
    Parameters:
        - edge_id: tuple. Edge-ID of edge from self.edges_dict
        - kwargs_text: dict with kwargs for plotting the text. All kwargs from "plt.text" can be used.
        - ax: axis-object to plot the text into.
    
    Returns: None
    
    Contributors: @Malte
    """
    edge = self.edges_dict[edge_id]
    T = edge['path'].ilength(edge['path'].length() / 2)
    xy_mid = edge['path'].point(T)
    (x_mid, y_mid) = (xy_mid.real, xy_mid.imag)
    ax.text(x_mid, y_mid, text, **kwargs_text)


def plot_layout(self, layout_style='default', show_IDs=True, show_svg_background=False, plt_or_ax=plt):
    """
    Plots the entire layout defined via the svg-IDs provided in self.svgID_to_edgeID_dict.
    A layout_style has to be passed to facilitate the plotting with kwargs.
    
    Parameters:
        - layout_style: str defining the layout-style to be used (optional, default is 'default').
            Use layout.define_layout_style to create a new layout-style if needed.
            Required keys of the layout_style-dict are:
                - 'kwargs_edgeTypes_dict'
                - 'kwargs_nodeTypes_dict'
        - show_IDs: currently unused.
        - show_svg_background: currently unused.
        - plt_or_ax: axis-object, optional (default is plt as abbreviation for matplotlib.pyplot). Can be either:
            - plt: matplotlib.pyplot. This will plot the layout into a created figure
            - ax: axis-object. This will plot the layout onto the given axis-object
    
    Returns: None
    
    Contributors: @Malte
    """
    ### ----- local variables ----- ###
    edge_ids_set = set(self.svgID_to_edgeID_dict.values())
    kwargs_edgeTypes_dict = self.layout_styles[layout_style]['kwargs_edgeTypes_dict']
    kwargs_nodeTypes_dict = self.layout_styles[layout_style]['kwargs_nodeTypes_dict']
    
    ### ----- figure initialization ----- ###
    if isinstance(plt_or_ax, ModuleType) and plt_or_ax == plt:
        fig,ax = plt.subplots(figsize=[12,8])
        ax.set_title('Layout of Airport {}'.format(self.airport_id))
    else:
        ax = plt_or_ax
        fig = plt.gcf()
        
    ### ----- plot edges ----- ###
    for edge_id in edge_ids_set:
        ## get kwargs for plotting dependent on edge-type
        edge_type = self.edges_dict[edge_id]['edge_type']
        if edge_type not in kwargs_edgeTypes_dict.keys():
            kwargs_line = kwargs_edgeTypes_dict['default']
        else:
            kwargs_line = kwargs_edgeTypes_dict[edge_type]
        ## plot line (only when kwargs are not None)
        if kwargs_line is not None:
            self.plot_edge(edge_id, kwargs_line, ax)
    
    ### ----- plot nodes ----- ###
    for node_id in self.nodes_dict.keys():
        node_type = self.nodes_dict[node_id]['node_type']
        if node_type not in kwargs_nodeTypes_dict.keys():
            kwargs_node = kwargs_nodeTypes_dict['default']
        else:
            kwargs_node = kwargs_nodeTypes_dict[node_type]
        ## plot node (only when kwargs are not None)
        if kwargs_node is not None:
            self.plot_node(node_id, kwargs_node, ax)
    
    ### ----- finish figure ----- ###
    try:
        ax.set_aspect('equal', adjustable='datalim')
    except RuntimeError:
        ax.set_aspect('equal')
    if isinstance(plt_or_ax, ModuleType) and plt_or_ax == plt:
        ax.invert_yaxis()
        fig.tight_layout(rect=[0, 0, 1, 0.96])
    
        
def plot_path(self, path, layout_style='default_path', title='', plt_or_ax=plt):
    """
    Plots a path either with the entire layout in the background, or onto an axis-object.
    A layout_style has to be passed to facilitate the plotting with kwargs.
    
    Parameters:
        - path: list of edge-IDs from self.edges_dict
        - layout_style: str defining the layout-style to be used (optional, default is 'default').
            Use layout.define_layout_style to create a new layout-style if needed.
            Required keys of the layout_style-dict are:
                - 'kwargs_edgeTypes_dict'
                - 'kwargs_nodeTypes_dict'
        - title: str; optional (default is ''). Title of the figure when plt_or_ax=plt (see below)
        - plt_or_ax: axis-object, optional (default is plt as abbreviation for matplotlib.pyplot). Can be either:
            - plt: matplotlib.pyplot. This will plot the path into a created figure, with the entire layout in the background
            - ax: axis-object. This will plot the path onto the given axis-object
    
    Returns:
        - line: plt.plot-object of one edge (i.e., path segment) for further use, e.g. for legends
    
    Contributors: @Malte
    """
    if isinstance(layout_style, str):
        layout_style = self.layout_styles[layout_style]
    kwargs_edgeTypes_dict = layout_style['kwargs_edgeTypes_dict'].copy()
    kwargs_nodeTypes_dict = layout_style['kwargs_nodeTypes_dict'].copy()
    
    ### ----- figure initialization ----- ###
    if isinstance(plt_or_ax, ModuleType) and plt_or_ax == plt:
        fig,ax = plt.subplots(figsize=[12,8])
        ax.set_title(title)
        ## plot layout into background
        self.plot_layout(layout_style='default_background', plt_or_ax=ax)
    else:
        ax = plt_or_ax  # do not plot layout into background as this should be handled in the function creating the ax-object
            
    ### ----- plot edges of path ----- ###
    for edge_id in path:
        if edge_id not in self.edges_dict.keys():
            continue
        ## get kwargs for plotting dependent on edge-type
        edge_type = self.edges_dict[edge_id]['edge_type']
        if edge_type not in kwargs_edgeTypes_dict.keys():
            kwargs_line = kwargs_edgeTypes_dict['default']
        else:
            kwargs_line = kwargs_edgeTypes_dict[edge_type]
        ## plot line (only when kwargs are not None)
        if kwargs_line is not None:
            line = self.plot_edge(edge_id, kwargs_line, ax)
    
    ### ----- plot nodes of path ----- ###
    nodes = set()
    [nodes.update(edge_id) for edge_id in path]
    for node_id in nodes:
        node_type = self.nodes_dict[node_id]['node_type']
        if node_type not in kwargs_nodeTypes_dict.keys():
            kwargs_node = kwargs_nodeTypes_dict['default']
        else:
            kwargs_node = kwargs_nodeTypes_dict[node_type]
        ## plot node (only when kwargs are not None)
        if kwargs_node is not None:
            self.plot_node(node_id, kwargs_node, ax)
        
    ### ----- finish figure ----- ###
    ax.set_aspect('equal')
    assert nodes
    self.zoom_to_selection(nodes, ax)
    if isinstance(plt_or_ax, ModuleType) and plt_or_ax == plt:
        # ax.invert_yaxis()
        fig.tight_layout(rect=[0, 0, 1, 0.96])
    
    ### ----- return 1 line-element of path to e.g. add legend to figure ----- ###
    return line


def zoom_to_selection(self, node_ids, ax, gap_factor=0.1):
    """
    Zooms the figure onto the passed nodes in node_ids.
    This function is helpful to e.g. zoom to a path.
    
    Parameters:
        - node_ids: list, set, or tuple. Node-IDs of self.nodes_dict
        - ax: axis-object to be zoomed.
    
    Contributors: @Malte
    """
    ### ----- zoom-settings for layout ----- ###
    ## determine min/max values for both x and y coordinates
    x_min = math.inf
    y_min = math.inf
    x_max = 0
    y_max = 0    
    for node_id in node_ids:
        x,y = self.nodes_dict[node_id]['pos_xy']
        x_min = min(x_min, x)
        x_max = max(x_max, x)
        y_min = min(y_min, y)
        y_max = max(y_max, y)
    ## zoom to selection
    xrange = x_max - x_min
    yrange = y_max - y_min
    ax.set_xlim(x_min - xrange*gap_factor, x_max + xrange*gap_factor)
    ax.set_ylim(y_max + yrange*gap_factor, y_min - yrange*gap_factor)  # to get inverted y-axis
