# -*- coding: utf-8 -*-
#
# Copyright 2021 Malte von der Burg
# Copyright 2021 Jorick Kamphof
#
# SPDX-License-Identifier: Apache-2.0

"""
Module: Airport_Layouts

Description:
    Creates a Layout-class instance based on a SVG-file converted from an xPlane *.dat-file.
    The layout is represented as a graph with nodes and edges, and e.g. packages like networkX can be used.
    Functions placed into sub-files of this module allow plotting or running calculations with the class-instance.

Contributors:
    - Malte von der Burg (@Malte)
    - Jorick Kamphof (@Jorick)
"""


#%% Import packages
## standard packages
import math
import time
import numpy as np
import matplotlib.pyplot as plt
import svgpathtools as spt
import xml.etree.ElementTree as Et
import re


#%% Class 
class Layout:
    """
    Based on an SVG-layout of an airport, this class creates the nodes- and edges-dicts of it.
    Furthermore, it encorporates further utility attributes and functions.
    """
    ### ----- class-imports ----- ###
    from ._Layout_utilFuncs import (calc_euclidean_dist,
                                    calc_heading_btw_coords,
                                    convert_bearing_to_heading,
                                    convert_heading_to_bearing)
    from ._Layout_plotFuncs import (define_default_layout_styles,
                                    define_layout_style,
                                    plot_node,
                                    plot_edge,
                                    plot_edge_segPts,
                                    plot_edge_direction,
                                    plot_text_on_edge,
                                    plot_layout,
                                    plot_path,
                                    zoom_to_selection,
                                    highlight_nodes,
                                    highlight_edges)
    ## add custom class-imports
    # import functions explicitely as above
    
    
    def __init__(self, svg_path, info_dict, devMode=False):
        """
        Contributors: @Malte, @Jorick
        """
        ### ----- general attributes ----- ###
        self.define_default_layout_styles()
        self.devMode = devMode
        
        ### ----- SVG-file ----- ###
        svg_path = svg_path.replace('\\','/')
        self.airport_id = svg_path[svg_path.rfind('/')+1:svg_path.rfind('.svg')]
        self.version = None
        if len(self.airport_id) > 4:
            self.version = self.airport_id[self.airport_id.rfind('-')+1:]
            self.airport_id = self.airport_id[:self.airport_id.rfind('-')]
        assert len(self.airport_id) == 4, 'airport_id must consist of exactly 4 letters, instead airport_id={}'.format(self.airport_id)
        assert self.airport_id != self.version
        tree = Et.parse(svg_path)
        root = tree.getroot()
        ## info_dict containing additional information on Runways, etc. 
        self.info_dict = info_dict
        self.WTC_dict = info_dict['WTC']
        
        ### ----- calibration (copied from python file "routing.py" from ENAC) ----- ###
        _cautra2svg = root.find('.//{http://www.w3.org/2000/svg}polyline[@id="cautra2svg"]')
        self._cautra2svg = list(map(float, re.split(r',| ', _cautra2svg.attrib["points"])))

        _svg2cautra = root.find('.//{http://www.w3.org/2000/svg}polyline[@id="svg2cautra"]')
        self._svg2cautra = list(map(float, re.split(r',| ', _svg2cautra.attrib["points"])))

        _svg2latlon = root.find('.//{http://www.w3.org/2000/svg}polyline[@id="svg2latlon"]')
        self._svg2latlon = list(map(float, re.split(r',| ', _svg2latlon.attrib["points"])))

        _latlon2svg = root.find('.//{http://www.w3.org/2000/svg}polyline[@id="latlon2svg"]')
        self._latlon2svg = list(map(float, re.split(r',| ', _latlon2svg.attrib["points"])))
        
        ### ----- create nodes and edges ----- ###
        self.import_nodes(root)
        self.import_edges(root)
        self.check_imports()
        self.enhance_imports()
        self.create_runway_data()
        self.create_pushpull_data()
        
        ### ----- initialize heuristics for aircraft and ground-vehicles ----- ###
        self.h_val_groups = []
        self.heuristics_dict = {'aircraft': {}, 'ground_vehicle': {}}
        
        ### ----- additional functions ----- ###
        self.create_nx_graph()
        
        
        
    #%% Import nodes from SVG-layout
    def import_nodes(self, root):
        """
        Contributors: @Malte, @Jorick
        """
        self.nodes_dict = {}
        ## intersection nodes
        for child in root.iter('{http://www.w3.org/2000/svg}g'):
            if 'id' in child.attrib and child.attrib['id'].startswith("intersection_"):
                node_id = int(child.attrib['id'].replace('intersection_node_',''))
                self.nodes_dict[node_id] = {'svg_id':child.attrib['id'],
                                            'node_type':'TWY_intersection',  # might be renamed below into 'RWY_intersection', 'SR_intersection', or 'Stopbar'
                                            'node_name':None,  # might be filled below with either RWY-name or Stopbar-name
                                            'pos_latlon':(float(child.attrib['latitude']), float(child.attrib['longitude'])),
                                            'pos_xy':(float(child.attrib['x']), float(child.attrib['y'])),
                                            'neighbors': set(), 
                                            'edges_to_node': set(),
                                            'edges_from_node': set()}
        ## termination nodes
        self.node_count_intersections = len(self.nodes_dict.keys())
        for child in root.iter('{http://www.w3.org/2000/svg}g'):
            if 'id' in child.attrib and child.attrib['id'].startswith('termination_'):
                node_id = int(child.attrib['id'].replace('termination_node_',''))
                node_id += self.node_count_intersections
                self.nodes_dict[node_id] = {'svg_id':child.attrib['id'],
                                            'node_type':'Termination_node',  # might be renamed below into 'Ramp'
                                            'node_name':None,
                                            'pos_latlon':(float(child.attrib['latitude']), float(child.attrib['longitude'])),
                                            'pos_xy':(float(child.attrib['x']), float(child.attrib['y'])),
                                            'neighbors': set(), 
                                            'edges_to_node': set(),
                                            'edges_from_node': set()}
        ## make svgID-to-nodeID-dict
        self.svgID_to_nodeID_dict = {vals['svg_id']:node_id for node_id,vals in self.nodes_dict.items()}
        
        ## Ramp names and ramp_dict + special points for remote holding and TET
        self.name2node_dict = {}  # dict for all node-names to node-IDs
        self.ramp2node_dict = {}
        self.ramp_dict = {}
        self.remhold2node_dict = {}
        self.remhold_dict = {}
        self.tug_base = set()  # node-IDs of the tug base
        self.n_buffer = None  # node-ID of buffer-stand
        node_ids_decouple = set()  # gather all decoupling points for sanity check
        node_ids_allclear = set()  # gather all all-clear points for sanity check
        parkings = root.find('.//{http://www.w3.org/2000/svg}g[@id="ParkingPositionElement"]')
        for child in parkings.iter('{http://www.w3.org/2000/svg}circle'):
            if 'node' in child.attrib:
                if child.attrib['node'].startswith('termination_'):
                    node_id = int(child.attrib['node'].replace('termination_node_',''))
                    node_id += self.node_count_intersections
                elif child.attrib['node'].startswith('intersection_'):
                    node_id = int(child.attrib['node'].replace('intersection_node_',''))
                if 'remhold' in child.attrib['id']:
                    self.nodes_dict[node_id]['node_type'] = 'RemoteHolding'
                    node_name = child.attrib['id'].removeprefix('remhold_').removesuffix('_TUD')
                    hp_info = self.info_dict['HPs'][node_name]
                    maxspan = int(hp_info['maxspan']) if not math.isnan(hp_info['maxspan']) else math.inf
                    minspan = int(hp_info['minspan']) if not math.isnan(hp_info['minspan']) else 0
                    hold_to_pass = hp_info['hold to pass']  # whether AC must hold to pass HP
                    used_for_IB = hp_info['inbound holding']
                    self.nodes_dict[node_id]['node_name'] = node_name
                    self.name2node_dict[node_name] = node_id
                    self.remhold2node_dict[node_name] = node_id
                    self.remhold_dict[node_id] = {'name': node_name,
                                                  'maxspan': maxspan,
                                                  'minspan': minspan,
                                                  'hold_to_pass': hold_to_pass,
                                                  'IB_holding': used_for_IB,
                                                  'edge_ids_access': set()}  # placeholder
                elif 'TET_base' in child.attrib['id']:
                    self.nodes_dict[node_id]['node_type'] = 'TET_base'
                    node_name = child.attrib['id'].removesuffix('_TUD')
                    self.nodes_dict[node_id]['node_name'] = node_name
                    self.name2node_dict[node_name] = node_id
                    self.tug_base.add(node_id)
                elif 'TET_decouple' in child.attrib['id']:
                    self.nodes_dict[node_id]['node_type'] = 'Decoupling_Point'
                    node_name = child.attrib['id'].removeprefix('TET_decouple_').removesuffix('_TUD')
                    node_name += '_dcp'  # to distinguish this point from decoupling-point with the same name
                    self.nodes_dict[node_id]['node_name'] = node_name
                    self.name2node_dict[node_name] = node_id
                    node_ids_decouple.add(node_id)
                elif 'TET_allclear' in child.attrib['id']:
                    self.nodes_dict[node_id]['node_type'] = 'AllClear_Point'
                    node_name = child.attrib['id'].removeprefix('TET_allclear_').removesuffix('_TUD')
                    node_name += '_acp'  # to distinguish this point from decoupling-point with the same name
                    self.nodes_dict[node_id]['node_name'] = node_name
                    self.name2node_dict[node_name] = node_id
                    node_ids_allclear.add(node_id)
                else:
                    assert not 'TUD' in child.attrib['id'], ('regular ramp-nodes should not contain suffix "TUD". '
                                                             + 'Check reasons.')
                    self.nodes_dict[node_id]['node_type'] = 'Ramp'
                    self.nodes_dict[node_id]['node_name'] = child.attrib['id']
                    self.name2node_dict[child.attrib['id']] = node_id
                    self.ramp2node_dict[child.attrib['id']] = node_id
                    if 'BUFFER' in child.attrib['id']:
                        assert self.n_buffer is None, 'more than one buffer-stand defined. Check ramifications.'
                        self.n_buffer = node_id
                        print('Buffer-stand defined at node {}.'.format(self.n_buffer))
                    try:
                        bearing = float(child.attrib['heading'])  # this is not in SVG-coordinates!
                    except:
                        bearing = None
                    self.ramp_dict[node_id] = {'name': child.attrib['id'], 'bearing': bearing,
                                               'edges_from_ramp': [], 'edges_to_ramp': [],
                                               'edges_entries': set(), 'pushback': {}}  # placeholder
        # assert len(self.tug_base) == 1, ('None or multiple tug bases defined, this is unexpected. '
        #                                  + 'Make sure they are not overwritten.')
        print('Tug base defined at node {}.'.format(list(self.tug_base)))
        
        ## RWY stopbar / holding points
        self.rwy2node_dict = {}
        holdingPoints = root.find('.//{http://www.w3.org/2000/svg}g[@id="HoldingPoints"]')
        holdingPoints_sub = holdingPoints.find('.//{http://www.w3.org/2000/svg}g[@id="Runways"]')
        # self.holdingPoints_rwys = holdingPoints_rwys
        for child in holdingPoints_sub.iter('{http://www.w3.org/2000/svg}g'):
            if child.attrib['id'] == 'Runways':
                continue
            hp_name = child.attrib['id']
            node_id = int(child.attrib['node'].replace('intersection_node_', ''))
            self.nodes_dict[node_id]['node_type'] = 'Stopbar'
            self.nodes_dict[node_id]['node_name'] = hp_name
            self.rwy2node_dict[hp_name] = node_id
            self.name2node_dict[hp_name] = node_id
        
        ## remote holding points
        holdingPoints_sub = holdingPoints.find('.//{http://www.w3.org/2000/svg}g[@id="Parkings"]')
        for child in holdingPoints_sub.iter('{http://www.w3.org/2000/svg}g'):
            if child.attrib['id'] == 'Parkings':
                continue
            hp_name = child.attrib['id']
            node_id = int(child.attrib['node'].replace('intersection_node_', ''))
            self.nodes_dict[node_id]['node_type'] = 'RemoteHolding'
            self.nodes_dict[node_id]['node_name'] = hp_name
            self.remhold2node_dict[hp_name] = node_id
            self.name2node_dict[hp_name] = node_id
        
        ## transfer-points
        self.transfer2node_dict = {}
        holdingPoints_sub = holdingPoints.find('.//{http://www.w3.org/2000/svg}g[@id="Transfers"]')
        for child in holdingPoints_sub.iter('{http://www.w3.org/2000/svg}g'):
            if child.attrib['id'] == 'Transfers':
                continue
            hp_name = child.attrib['id']
            node_id = int(child.attrib['node'].replace('intersection_node_', ''))
            self.nodes_dict[node_id]['node_type'] = 'Transfer'
            self.nodes_dict[node_id]['node_name'] = hp_name
            self.transfer2node_dict[hp_name] = node_id
            self.name2node_dict[hp_name] = node_id
        
        ## deicing-points, also used for tug-decoupling and tug-coupling
        self.deicing2node_dict = {}
        holdingPoints_sub = holdingPoints.find('.//{http://www.w3.org/2000/svg}g[@id="Deicing"]')
        for child in holdingPoints_sub.iter('{http://www.w3.org/2000/svg}g'):
            if child.attrib['id'] == 'Deicing':
                continue
            hp_name = child.attrib['id']
            node_id = int(child.attrib['node'].replace('intersection_node_', ''))
            if 'type' in child.attrib.keys():
                assert False, 'implement how to handle this part'
            else:
                node_type = 'Deicing'
            self.nodes_dict[node_id]['node_type'] = node_type
            self.nodes_dict[node_id]['node_name'] = hp_name
            self.deicing2node_dict[hp_name] = node_id
            self.name2node_dict[hp_name] = node_id
        
        ## taxibot-points, used for tug-decoupling and tug-coupling
        self.tugPoints2node_dict = {}
        holdingPoints_sub = holdingPoints.find('.//{http://www.w3.org/2000/svg}g[@id="Taxibot"]')
        for child in holdingPoints_sub.iter('{http://www.w3.org/2000/svg}g'):
            if child.attrib['id'] == 'Taxibot':
                continue
            hp_name = child.attrib['id']
            if child.attrib['node'].startswith('termination_'):
                node_id = int(child.attrib['node'].replace('termination_node_',''))
                node_id += self.node_count_intersections
            elif child.attrib['node'].startswith('intersection_'):
                node_id = int(child.attrib['node'].replace('intersection_node_',''))
            if 'type' in child.attrib.keys():
                ## tug base
                if child.attrib['type'].lower().find('base') >= 0:
                    self.tug_base.add(node_id)
                else:
                    assert False, 'implement how to handle this part'
            else:
                node_type = 'Tugs'
            self.nodes_dict[node_id]['node_type'] = node_type
            self.nodes_dict[node_id]['node_name'] = hp_name
            self.tugPoints2node_dict[hp_name] = node_id
            self.name2node_dict[hp_name] = node_id
        
        ## RWY thresholds
        rwy_thresholds = root.find('.//{http://www.w3.org/2000/svg}g[@id="RunwayThreshold"]')
        self.runways_dict = {}
        self.decouple2allclear_dict = {}
        rwy_dir_dict = {}
        for child in rwy_thresholds.iter('{http://www.w3.org/2000/svg}path'):
            rwy_strip_name = child.attrib['id']
            if rwy_strip_name not in self.info_dict['runways'].keys():
                print('WARNING: Runway-name "{}" does not exist in file "LAYOUT_AdditionalInformation". I will skip this entry.'.format(rwy_strip_name))
                continue
            rwy_dirs = rwy_strip_name.split('/')
            for rwy_dir in rwy_dirs:
                rwy_dir_dict[rwy_dir] = rwy_strip_name
            info_stopbars = self.info_dict['runways'][rwy_strip_name]['Stopbars']
            info_stopbars_RET = self.info_dict['runways'][rwy_strip_name]['RETs']
            # some stopbars consist of multiple nodes in the layout, each having an own ID. Therefore, extract these IDs by matching their name with the info-names.
            stopbars = set()
            stopbar_names = set()
            stopbars_RET = set()
            for stopbar in self.rwy2node_dict.keys():
                stopbar_name = stopbar.split('_')[0]
                if stopbar_name in info_stopbars:
                    stopbars.add(self.rwy2node_dict[stopbar])
                    stopbar_names.add(stopbar)
                if stopbar_name in info_stopbars_RET:
                    stopbars_RET.add(self.rwy2node_dict[stopbar])

            ## add selected decoupling points (from LAYOUT_AdditionalInformation.xlsx) and all-clear points (fixed for each decoupling point)
            tug_decoupling = self.info_dict['runways'][rwy_strip_name]['Tug decoupling']
            tug_decoupling_dict = {}
            for decouple_name in tug_decoupling:
                if decouple_name + '_dcp' in self.name2node_dict:
                    node_id_decouple = self.name2node_dict[decouple_name + '_dcp']
                else:
                    node_id_decouple = self.name2node_dict[decouple_name]
                node_ids_decouple.add(node_id_decouple)
                node_id_allclear = self.name2node_dict[decouple_name + '_acp']
                node_ids_allclear.add(node_id_allclear)
                if decouple_name in self.remhold2node_dict:
                    strategy = 'out-flow'
                else:
                    strategy = 'in-flow'
                tug_decoupling_dict[node_id_decouple] = {'name_decouple_point': decouple_name,
                                                         'decoupling_node': node_id_decouple,
                                                         'tug_all_clear_node': node_id_allclear,
                                                         'strategy': strategy}
                self.decouple2allclear_dict[node_id_decouple] = node_id_allclear
            
            ## outbound holding
            remhold_OB_names = self.info_dict['runways'][rwy_strip_name]['Outbound HPs']
            remhold_OB_nodes = {self.name2node_dict[k] for k in remhold_OB_names}
            ## create dict for runway-stip
            self.runways_dict[rwy_strip_name] = {'rwy_dirs':rwy_dirs,
                                                 'rwy_bearings':[],
                                                 'stopbars':stopbars, 
                                                 'stopbars_RET':stopbars_RET,
                                                 'stopbar_names':stopbar_names,
                                                 'tug_decoupling':tug_decoupling_dict,
                                                 'outbound_holding': remhold_OB_nodes}
            
        for child in rwy_thresholds.iter('{http://www.w3.org/2000/svg}circle'):
            rwy_dir = child.attrib['id'].replace('THR_','')
            rwy_strip_name = rwy_dir_dict[rwy_dir]
            pos_start = (float(child.attrib['cx']), float(child.attrib['cy']))
            node_start = None
            for node_id,node in self.nodes_dict.items():
                if np.isclose(node['pos_xy'], pos_start).all():
                    node_start = node_id
                    break
            self.runways_dict[rwy_strip_name][rwy_dir] = {'pos_start':pos_start, 'node_start':node_start}
        ## create set of all runway-names + mapping of runway-name to rwyStrip-name
        self.runways = set()
        [self.runways.update(rwy_data['rwy_dirs']) for rwy_data in self.runways_dict.values()]
        self.rwy2strip_dict = {v:k for k in self.runways_dict.keys() for v in self.runways_dict[k]['rwy_dirs']}
        ## check for unused decoupling points
        if node_ids_decouple.difference(self.decouple2allclear_dict.keys()):
            unused_dcps = node_ids_decouple.difference(self.decouple2allclear_dict.keys())
            unused_dcps_dict = {k: self.nodes_dict[k]['node_name'] for k in unused_dcps}
            print('Unused decoupling points detected: {}'.format(unused_dcps_dict))
        ## check for unused all-clear points
        if node_ids_allclear.difference(self.decouple2allclear_dict.values()):
            unused_acps = node_ids_allclear.difference(self.decouple2allclear_dict.values())
            unused_acps_dict = {k: self.nodes_dict[k]['node_name'] for k in unused_acps}
            print('Unused all-clear points detected: {}'.format(unused_acps_dict))
        
        
        
    #%% Import edges from SVG-layout
    def import_edges(self, root):
        """
        Contributors: @Malte, @Jorick
        """
        edges_dict_unsorted = {}
        edge_ids4sort = []
        edge_errors = []
        self.svgID_to_edgeID_dict = {}
        self._svgEdges_entries_dict = {}  # temporarily defined, deleted once layout is created
        self._svgEdges_pushback_dict = {}  # temporarily defined to create pushback-paths
        self._svgEdges_pull_dict = {}  # temporarily defined to create pull-paths
        for child in root.iter('{http://www.w3.org/2000/svg}path'):
            if 'id' in child.attrib and child.attrib['id'].startswith('edge_'):
                ## starting node
                node_start = -1
                if child.attrib['bound1'].startswith('intersection_'):
                    node_start = int(child.attrib['bound1'].replace('intersection_node_',''))
                    node_start4sort = node_start
                elif child.attrib['bound1'].startswith('termination_'):
                    node_start = int(child.attrib['bound1'].replace('termination_node_','')) + self.node_count_intersections
                    node_start4sort = node_start
                else:
                    node_start = None
                    node_start4sort = -1
                ## ending node
                node_end = -1
                if child.attrib['bound2'].startswith('intersection_'):
                    node_end = int(child.attrib['bound2'].replace('intersection_node_',''))
                    node_end4sort = node_end
                elif child.attrib['bound2'].startswith('termination_'):
                    node_end = int(child.attrib['bound2'].replace('termination_node_','')) + self.node_count_intersections
                    node_end4sort = node_end
                else:
                    node_end = None
                    node_end4sort = -1
                ## generate edge-ID and reverse edge-ID
                edge_id = (node_start, node_end)
                edge_id_rev = (node_end, node_start)
                if edge_id in edges_dict_unsorted.keys():
                    print('WARNING: edge-id = {} exists already, SVG-IDs: {} and {}. The latter one will NOT be added to the layout.'.format(edge_id, edges_dict_unsorted[edge_id]['svg_id'], child.attrib['id']))
                    continue
                assert edge_id not in edges_dict_unsorted.keys(), 'edge_id already exists: multiple edges are not allowed.'
                self.svgID_to_edgeID_dict[child.attrib['id']] = edge_id
                ## get SVG-name
                edge_maxspan = math.inf
                if 'edgeNameFromXPlane' in child.attrib.keys():
                    svg_name = child.attrib['edgeNameFromXPlane']
                    ## set maximal wingspan (maxspan) if part of SVG-name
                    if 'maxspan' in svg_name:
                        maxspan_idx = svg_name.find('maxspan')+len('maxspan')+1
                        edge_maxspan = int(svg_name[maxspan_idx:].split('_')[0])
                        svg_name = svg_name.replace('_maxspan_{}'.format(edge_maxspan), '')  # maxspan should not be in edge-name
                    ## only use names with "TUD" but without "Linear Feature" in them
                    assert child.attrib['type'] in ('runway', 'taxiway', 'service')
                    if (svg_name.find('TUD') >= 0 or child.attrib['type'] == 'service') and svg_name.find('Linear Feature') < 0:
                        edge_name = None
                        if svg_name.find('TUD') >= 0:
                            edge_name = svg_name.split('_TUD')[0] #split and take first part of the split, as for some edges the svg_generator generates _TUD_2, _TUD_3 etc
                        edge_type = 'TWY_edge'  # default type
                        if svg_name.lower().find('serviceroad') >= 0:
                            edge_type = 'ServiceRoad'
                            edge_name = None
                            # edge_name = 'SRxx'
                        if svg_name.lower().find('center_serviceroad') >= 0:
                            edge_type = 'CenterServiceRoad'
                            edge_name = None
                        elif svg_name.lower().find('stand') >= 0:
                            edge_type = 'Stand'
                            edge_name = svg_name.split('_')[0]
                        
                        ## entries and exits to remote holding points
                        if svg_name.lower().find('entry_exit') >= 0:
                            hp_names = svg_name.split('_')[0].split('&')
                            for hp in hp_names:
                                hp_node = self.name2node_dict[hp]
                                hp_dict = self.remhold_dict[hp_node]
                                hp_dict['edge_ids_access'].update({edge_id, edge_id_rev})
                        
                        ## Push back paths and push-pull paths
                        if svg_name.lower().find('pb') > 0 or svg_name.lower().find('pull') >= 0:
                            if not 'TWY' in svg_name:
                                edge_type = 'PB/PUSH-PULL_placeholder'
                                edge_name = None
                            svg_name_new = svg_name.split('_TUD')[0] #split and take first part of the split, as for some edges the svg_generator generates _TUD_2, _TUD_3 etc
                            svg_name_split = svg_name_new.split('-') #split between pb or pushpull - which separates different pull/push types in xplane name
                            
                            for pushback_variant in svg_name_split:
                                if 'TWY' in pushback_variant:
                                    continue  # special case when PB-path coincides with named TWY
                                ## Push paths
                                if not pushback_variant.lower().find('pull') >= 0: 
                                    pushback_variant_split = pushback_variant.split('_')
                                    ## add standard push-back paths, and those for special ICAO categories
                                    if pushback_variant.lower().find('pb@') <0: #if name does not have pb@ (indicating that it is only for certain cat)
                                        gates = pushback_variant_split[0] #for pushback paths, the gates are always the first part of the split
                                        sType = 'Standard'
                                    elif pushback_variant.lower().find('pb@d') >= 0: #if there is a special push-back path for ICAO D and higher
                                        gates = pushback_variant_split[0] #for pushback paths, the gates are always the first part of the split
                                        sType = 'ICAO-D'
                                    
                                    ## Add edge to all gates for which this is a push
                                    gates_split = gates.split('&')
                                    for gate in gates_split:
                                        if not gate in self._svgEdges_pushback_dict.keys(): # create dict if it does not exist for this gate yet
                                            self._svgEdges_pushback_dict[gate] = {'Standard': [], 'ICAO-A': [],'ICAO-B': [],'ICAO-C': [],'ICAO-D': [],'ICAO-E': [],'ICAO-F': []}
                                        self._svgEdges_pushback_dict[gate][sType].extend([edge_id, edge_id_rev])
                                
                                ## Pull paths
                                else:
                                    pushback_variant_split = pushback_variant.split('_')
                                    #print('PULL:', pushback_variant_split)
                                    
                                    if pushback_variant.lower().find('pull@') <0: #if name does not have pull@ (indicating that it is only for certain cat)
                                        gates = pushback_variant_split[1] #for pushback paths, the gates are always the second part of the split    
                                        sType = 'Standard'
                                    elif pushback_variant.lower().find('pull@d') >= 0: #if there is a special pull path for ICAO D and higher
                                        gates = pushback_variant_split[1] #for pushback paths, the gates are always the second part of the split  
                                        sType = 'ICAO-D'
                                        
                                    # Add edge to all gates for which this is a pull edge
                                    gates_split = gates.split('&')
                                    for gate in gates_split:
                                        #print('Add pull path for:', gate, 'sType:', sType)
                                        if not gate in self._svgEdges_pull_dict.keys(): # create dict if it does not exist for this gate yet
                                            self._svgEdges_pull_dict[gate] = {'Standard': [], 'ICAO-A': [],'ICAO-B': [],'ICAO-C': [],'ICAO-D': [],'ICAO-E': [],'ICAO-F': []} #already create dict for pull maneuvers here (those always need a push first)
                                        self._svgEdges_pull_dict[gate][sType].extend([edge_id, edge_id_rev])
                        
                        ## Entry paths
                        if svg_name.lower().find('entry') >= 0:
                            svg_name_split = svg_name.split('_')
                            if svg_name_split[0] in self._svgEdges_entries_dict.keys():
                                self._svgEdges_entries_dict[svg_name_split[0]].append(child.attrib['id'])
                            else:
                                self._svgEdges_entries_dict[svg_name_split[0]] = [child.attrib['id']]
                            edge_type = 'entry_placeholder'
                            edge_name = None
                    else:
                        edge_name = None
                        edge_type = 'TWY_edge'
                
                ## parse path + check if start-node is fitting path
                path = spt.parse_path(child.attrib['d'])
                try:
                    if node_start is not None:
                        if self.nodes_dict[node_start]['pos_xy'] != (path[0][0].real, path[0][0].imag):
                            edge_errors.append(edge_id)
                    else:
                        if self.nodes_dict[node_end]['pos_xy'] != (path[-1][-1].real, path[-1][-1].imag):
                            edge_errors.append(edge_id)
                except:
                    edge_errors.append(edge_id)
                ## get segment types and lengths
                d_split = child.attrib['d'].split(' ')
                seg_types = []
                for elem in d_split:
                    if elem.isalpha() and elem != 'M':
                        seg_types.append(elem)
                seg_lengths = [i.length()*6 for i in path]  # factor *6 is necessary to get correct length of path in [m]!
                ## calc heading of ends of each segment and entire path
                seg_headings = []
                for seg in path:
                    coords = np.array(seg)
                    if np.diff(coords[:2]) != 0:
                        heading_start = self.calc_heading_btw_coords((coords[0].real, coords[0].imag), (coords[1].real, coords[1].imag), y_inverted=True)  # "y_inverted=True" is due to inverted coords in SVG-file
                    else:  # in the case that start- and control-point are the same 
                        seg_len = round(seg.length()*6*10)  # length in [dm]
                        hPt = seg.point(1/seg_len)  # get point 10cm from start-point
                        heading_start = self.calc_heading_btw_coords((coords[0].real, coords[0].imag), (hPt.real, hPt.imag), y_inverted=True)
                    if np.diff(coords[-2:]) != 0:
                        heading_end = self.calc_heading_btw_coords((coords[-2].real, coords[-2].imag), (coords[-1].real, coords[-1].imag), y_inverted=True)  # will be equal to heading_start for a Bezier-Line
                    else:  # in the case that end- and control-point are the same 
                        seg_len = round(seg.length()*6*10)  # length in [dm]
                        hPt = seg.point((seg_len-1)/seg_len)  # get point 10cm before end-point
                        heading_end = self.calc_heading_btw_coords((hPt.real, hPt.imag), (coords[-1].real, coords[-1].imag), y_inverted=True)
                    seg_headings.append((heading_start, heading_end))
                edge_heading = (seg_headings[0][0], seg_headings[-1][-1])
                ## calc radius of curvature for segments
                r_mins = []
                r_maxs = []
                r_meds = []
                r_mids = []
                r_error_isStraight = []
                for idx,seg in enumerate(path):
                    if seg_types[idx] != 'L':
                        step = 1 / (math.ceil(seg.length()) * 1)  # get step-size based on length in [dm] = approx. 10cm-steps
                        T_array = np.array(np.arange(0,1+step,step))  # creates values on interval between [0, 1]
                        r_array = np.zeros(T_array.size)
                        for n,T in enumerate(T_array):
                            try:
                                r_array[n] = 6 / seg.curvature(T)  # factor *6 is necessary to get correct length of path in [m]!
                            except (ValueError, ZeroDivisionError, FloatingPointError):
                                r_array[n] = math.inf
                        try:
                            r_mid = 6 / seg.curvature(0.5)  # factor *6 is necessary to get correct length of path in [m]!
                        except (ZeroDivisionError, FloatingPointError):
                            r_mid = math.inf
                            r_error_isStraight.append((edge_id, seg_types, idx, seg_lengths[idx]))
                        r_mins.append(r_array.min())
                        r_maxs.append(r_array.max())
                        r_meds.append(np.median(r_array))
                        r_mids.append(r_mid)
                    else:
                        r_mins.append(math.inf)
                        r_maxs.append(math.inf)
                        r_meds.append(math.inf)
                        r_mids.append(math.inf)
                if r_error_isStraight:
                    print('Curvature issues of segments occured: found curvy segments ("Q" or "C") that have no curvature: (edge-ID, seg-types, seg-index, seg-length)')
                    print(r_error_isStraight)
                ## insert values. Hint: those lists that are reversed IN PLACE below need to have .copy() to remain un-reversed in the dict.
                edges_dict_unsorted[edge_id] = {'edge_id': edge_id,
                                                'edge_type': edge_type,
                                                'edge_name': edge_name,
                                                'svg_id': child.attrib['id'],
                                                'svg_name': svg_name,
                                                'edge_svg_inverse': False,
                                                'path_unparsed': child.attrib['d'],
                                                'path': path,
                                                'length': float(child.attrib['pathLength']),
                                                'radius': np.mean(r_meds),
                                                'heading': edge_heading,
                                                'slope': float(child.attrib['slope']),
                                                'maxspan': edge_maxspan,
                                                'v_limit': math.inf,
                                                'seg_types': seg_types.copy(),
                                                'seg_lengths': seg_lengths.copy(),
                                                'seg_headings': seg_headings,
                                                'seg_r_mins': r_mins.copy(),
                                                'seg_r_maxs': r_maxs.copy(),
                                                'seg_r_meds': r_meds.copy(),
                                                'seg_r_mids': r_mids.copy(),
                                                'use_cost_factor': 1}
                
                ### ----- create reverse edge ----- ###
                ## revert its path
                path_reversed = path.reversed()
                seg_types.reverse(); seg_lengths.reverse(); r_mins.reverse(); r_maxs.reverse(); r_meds.reverse(); r_mids.reverse()  # lists are reversed in place
                # recalc heading of reversed path
                seg_headings = []
                for seg in path_reversed:
                    coords = np.array(seg)
                    if np.diff(coords[:2]) != 0:
                        heading_start = self.calc_heading_btw_coords((coords[0].real, coords[0].imag), (coords[1].real, coords[1].imag), y_inverted=True)  # "y_inverted=True" is due to inverted coords in SVG-file
                    else:  # in the case that start- and control-point are the same 
                        seg_len = round(seg.length()*6*10)  # length in [dm]
                        hPt = seg.point(1/seg_len)  # get point 10cm from start-point
                        heading_start = self.calc_heading_btw_coords((coords[0].real, coords[0].imag), (hPt.real, hPt.imag), y_inverted=True)
                    if np.diff(coords[-2:]) != 0:
                        heading_end = self.calc_heading_btw_coords((coords[-2].real, coords[-2].imag), (coords[-1].real, coords[-1].imag), y_inverted=True)  # will be equal to heading_start for a Bezier-Line
                    else:  # in the case that end- and control-point are the same 
                        seg_len = round(seg.length()*6*10)  # length in [dm]
                        hPt = seg.point((seg_len-1)/seg_len)  # get point 10cm before end-point
                        heading_end = self.calc_heading_btw_coords((hPt.real, hPt.imag), (coords[-1].real, coords[-1].imag), y_inverted=True)
                    seg_headings.append((heading_start, heading_end))
                edge_heading = (seg_headings[0][0], seg_headings[-1][-1])
                edges_dict_unsorted[edge_id_rev] = {'edge_id': edge_id_rev,
                                                    'edge_type': edge_type,
                                                    'edge_name': edge_name,
                                                    'svg_id': child.attrib['id'],
                                                    'svg_name': svg_name,
                                                    'edge_svg_inverse': True,
                                                    'path_unparsed': child.attrib['d'],
                                                    'path': path_reversed,
                                                    'length': float(child.attrib['pathLength']),
                                                    'radius': np.mean(r_meds),
                                                    'heading': edge_heading,
                                                    'slope': (-1)*float(child.attrib['slope']),  # (-1)-factor to reverse slope
                                                    'maxspan': edge_maxspan,
                                                    'v_limit': math.inf,
                                                    'seg_types': seg_types,
                                                    'seg_lengths': seg_lengths,
                                                    'seg_headings': seg_headings,
                                                    'seg_r_mins': r_mins,
                                                    'seg_r_maxs': r_maxs,
                                                    'seg_r_meds': r_meds,
                                                    'seg_r_mids': r_mids,
                                                    'use_cost_factor': 1}
                ## use edge_id as list for sorting
                edge_ids4sort.append([node_start4sort, node_end4sort])
                edge_ids4sort.append([node_end4sort, node_start4sort])
        ## print edge-errors:
        if edge_errors:
            print('\nEdge issues occured: edge-direction is swapped for edge-IDs\n{}\n'.format(edge_errors))
        ## sort edges_dict (easier for debugging)
        edge_ids4sort.sort()
        for i,elem in enumerate(edge_ids4sort):
            if elem[0] == -1:
                edge_ids4sort[i][0] = None
            elif elem[1] == -1:
                edge_ids4sort[i][1] = None
        self.edges_dict = {tuple(k):edges_dict_unsorted[tuple(k)] for k in edge_ids4sort}
        
        
        
    #%% Check whether data underlying nodes and edges is complete 
    def check_imports(self):
        """
        Contributors: @Jorick, @Malte
        """
        ### ----- check for nodes within 1m of each other ----- ###
        nodes_to_check = set()
        for idx,node_id in enumerate(list(self.nodes_dict.keys())):
            node_pos = self.nodes_dict[node_id]['pos_xy']
            for node_id_2nd in list(self.nodes_dict.keys())[idx:]:
                if node_id == node_id_2nd:
                    continue
                dist = self.calc_euclidean_dist(node_pos, self.nodes_dict[node_id_2nd]['pos_xy'])
                if dist < 1:
                    nodes_to_check.update((node_id, node_id_2nd))
        if nodes_to_check:
            self.highlight_nodes(nodes_to_check)
            plt.gca().set_title('Nodes within 1m of each other: zoom in to check for incorrectly placed nodes in SVG layout')
        
        ### ----- check remaining None nodes ----- ###
        self.None_nodes = []
        for edge_id in self.svgID_to_edgeID_dict.values():
            if edge_id.count(None):
                path = self.edges_dict[edge_id]['path']
                if edge_id[0] == None:
                    coords = path[0][0]
                elif edge_id[1] == None:
                    coords = path[-1][-1]
                self.None_nodes.append((coords.real, coords.imag))
        if self.None_nodes:
            print('\n======================================================================================')
            print('WARNING: There are still None-nodes existent: {}'.format(self.None_nodes))
            print('======================================================================================\n')
        
        ### ----- show Termination-nodes ----- ###
        nids_termination = [nid for nid,n in self.nodes_dict.items() if 'Termination' in n['node_type']]
        if nids_termination:
            self.highlight_nodes(nids_termination)
            plt.gca().set_title('Termination-nodes: check for incorrectly placed nodes in SVG layout')
            
        ### ----- check if there is a push-back path and entry for all gates ----- ###
        no_push_back_path = []
        for gate_id in self.ramp2node_dict.keys():
            if not gate_id in list(self._svgEdges_pushback_dict.keys()):
                no_push_back_path.append(gate_id)
        if len(no_push_back_path) > 0:
            print('\n======================================================================================')
            print('WARNING: There are no pushback-paths defined in Xplane for stands: {}. '.format(no_push_back_path)
                  + 'This is not neccesarily an error, but verify that these stands are non-pushback stands.')
            print('======================================================================================\n')
            if self.devMode:
                print_no_pb_path = input('Plot stands without pushback-path? Press "y"=yes or "n"=no.\n').lower() == 'y'
                if print_no_pb_path:
                    self.highlight_nodes(no_push_back_path)
                    plt.gca().set_title('Stands without pushback-path')
        
        no_entry_path = []
        for gate_id in self.ramp2node_dict.keys():
            if not gate_id in list(self._svgEdges_entries_dict.keys()):
                no_entry_path.append(gate_id)
        if len(no_entry_path) > 0:
            print('\n======================================================================================')
            print('WARNING: There are no stand entry-paths defined in Xplane for stands: {}.'.format(no_entry_path))
            print('======================================================================================\n')
            if self.devMode:
                print_no_entry_path = input('Plot stands without entry-path? Press "y"=yes or "n"=no.\n').lower() == 'y'
                if print_no_entry_path:
                    self.highlight_nodes(no_entry_path)
                    plt.gca().set_title('Stands without entry-path')
        
        
        
    #%% Enhance SVG-data with inferred node- and edge-properties
    def enhance_imports(self):
        """
        Contributors: @Malte, @Jorick
        """
        ### ----- add node neighbors to nodes_dict, add edges_from and edges_to to nodes_dict ----- ###
        for edge_id in self.edges_dict.keys():
            (node_start, node_end) = edge_id[:2]
            if node_start == None:  # if start_node is a termination node, pass
                self.nodes_dict[node_end]['edges_to_node'].add(edge_id)  #???!MvdB: added this, as this is still possible
            elif node_end == None:  # if end_node is a termination node, pass
                self.nodes_dict[node_start]['neighbors'].add(node_end)  #???!MvdB: added this, as this is still possible
                self.nodes_dict[node_start]['edges_from_node'].add(edge_id)
            else:
                self.nodes_dict[node_start]['neighbors'].add(node_end)
                self.nodes_dict[node_start]['edges_from_node'].add(edge_id)
                self.nodes_dict[node_end]['edges_to_node'].add(edge_id)
        
        ### ----- extract ramp-edges ----- ###
        self.ramp_edges_set = set()
        for node_id in list(self.ramp2node_dict.values()):
            edges_from = self.nodes_dict[node_id]['edges_from_node']
            edges_to = self.nodes_dict[node_id]['edges_to_node']
            for edge_from_id in edges_from:
                if self.edges_dict[edge_from_id]['edge_type'] == 'Stand':
                    self.ramp_edges_set.add(edge_from_id)
                    self.ramp_dict[node_id]['edges_from_ramp'].append(edge_from_id)
            for edge_to_id in edges_to:
                if self.edges_dict[edge_to_id]['edge_type'] == 'Stand':
                    self.ramp_edges_set.add(edge_to_id)
                    self.ramp_dict[node_id]['edges_to_ramp'].append(edge_to_id)
        
        ### ----- correct naming of ServiceRoad intersections ----- ###
        for node_id, node in self.nodes_dict.items():
            if node['node_type'] != 'TWY_intersection':
                continue
            cond = True
            for edge_id in node['edges_from_node']:
                edge = self.edges_dict[edge_id]
                if 'ServiceRoad' not in edge['edge_type']:
                    cond = False
                    break
            if not cond:
                continue
            node['node_type'] = 'SR_intersection'
        
        ### ----- add next_edges to all edges in edges_dict ----- ###
        edge_sharpCorner = []
        for edge_id in self.edges_dict.keys():
            next_edges = set()
            next_edges_isSlowTurn = {}
            heading_ownEnd = self.edges_dict[edge_id]['heading'][1]
            (node_start, node_end) = edge_id[:2]
            if node_end is not None:
                next_edge_ids = self.nodes_dict[node_end]['edges_from_node'].copy()
                for next_edge_id in next_edge_ids:
                    if next_edge_id[:2] == (node_end, node_start):  # remove edge(s) to start-node of current edge
                        continue
                    heading_nextStart = self.edges_dict[next_edge_id]['heading'][0]
                    heading_diff = min( (heading_ownEnd-heading_nextStart)%360 , (heading_nextStart-heading_ownEnd)%360 )
                    if heading_diff < 135:  # only add edge-ID to next_edges if not overly sharp turn
                        next_edges.add(next_edge_id)
                        isSlowTurn = heading_diff > 30  # slow-turn based on edge-radius is not included here, as it is vehicle-specific
                        next_edges_isSlowTurn[next_edge_id] = isSlowTurn
            # insert values into edge-dict + check for sharp turn
            self.edges_dict[edge_id].update({'next_edges':next_edges, 'next_edges_isSlowTurn':next_edges_isSlowTurn})
            if sum(next_edges_isSlowTurn.values()) > 0:
                edge_sharpCorner.append(edge_id)
        if edge_sharpCorner:
            print('\nEdge issues occured: sharp turns may occur for edge-IDs\n{}\n'.format(edge_sharpCorner))
        
        ### ----- get next-edgeIDs for switching direction at end-node of edge ----- ###
        for edge_id, edge in self.edges_dict.items():
            node_id_end = edge_id[1]
            edge_ids_from_node = self.nodes_dict[node_id_end]['edges_from_node']
            edge_ids_next_regular = [k for k,v in edge['next_edges_isSlowTurn'].items() if not v]
            edge_ids_dirSwitch = edge_ids_from_node.difference(edge_ids_next_regular)
            edge['next_edges_dirSwitch'] = edge_ids_dirSwitch
        
        
        
    #%% create runways_dict
    def create_runway_data(self):
        """
        Contributors: @Malte
        """
        ## gather special edges that have a special function for the runways
        edges_special_RWY = {'crossing': {}, 'ahead': {}}
        for edge_id, edge in self.edges_dict.items():
            edge_name = edge['edge_name']
            if not edge_name:
                continue
            if 'crossing' in edge_name:
                rwy_strip = None
                for k in self.runways_dict.keys():
                    if k in edge_name:
                        rwy_strip = k
                        break
                assert rwy_strip
                data = edges_special_RWY['crossing'].setdefault(rwy_strip, set())
                data.add(edge_id)
            elif 'ahead' in edge_name:
                rwy = None
                for k in self.runways:
                    if k in edge_name:
                        rwy = k
                        break
                assert rwy
                data = edges_special_RWY['ahead'].setdefault(rwy, set())
                data.add(edge_id)
        
        ## create entry for each RWY-strip
        for rwy_strip, vals in self.runways_dict.items():
            (rwy_dir1, rwy_dir2) = vals['rwy_dirs']
            dir1_pos_xy = vals[rwy_dir1]['pos_start']
            dir2_pos_xy = vals[rwy_dir2]['pos_start']
            # hint: for the correct heading, the y-axis needs to be inverted!
            dir1_heading = self.calc_heading_btw_coords(dir1_pos_xy, dir2_pos_xy, y_inverted=True)
            dir2_heading = self.calc_heading_btw_coords(dir2_pos_xy, dir1_pos_xy, y_inverted=True)
            vals['rwy_bearings'] = [self.convert_heading_to_bearing(dir1_heading, 1), self.convert_heading_to_bearing(dir2_heading, 1)]
            vals[rwy_dir1]['heading'] = dir1_heading
            vals[rwy_dir2]['heading'] = dir2_heading
            
            ## obtain the nodes, edges, and exit-edges of both runway-directions (rwy_dirs)
            stopbars_io = set()
            edge_ids_exits = set()
            edge_ids_entries = set()
            for idx,rwy_dir in enumerate(vals['rwy_dirs']):
                assert len(vals['rwy_dirs'])==2, 'in creation of runways_dict[{}][{}]: more/less than 2 runway directions.'.format(rwy_strip, rwy_dir)
                vals_rwy_dir = vals[rwy_dir]
                ## get initial edge from start-node
                rwy_node_start = vals_rwy_dir['node_start']
                edges_from_start = list(self.nodes_dict[rwy_node_start]['edges_from_node'])
                assert len(edges_from_start) == 1, ('in creation of runways_dict[{}][{}]: '.format(rwy_strip, rwy_dir)
                                                    + 'more/less than 1 edge are connected to its threshold-node.'
                                                    + 'edges_from_start={} for node={}'.format(edges_from_start, rwy_node_start))
                edge_now = edges_from_start[0]
                rwy_nodes = [rwy_node_start, edge_now[1]]
                rwy_edges = [edge_now]
                rwy_length = 0
                rwy_exitEdges = {}
                rwy_rev_entryEdges = {}
                stopbars_exits = {'node_ids':set(), 'edge_ids':set()}
                ## check next edges as long as they exist:
                while edge_now:
                    rwy_length += self.edges_dict[edge_now]['length']
                    next_edges = list(self.edges_dict[edge_now]['next_edges'])
                    edge_now = None
                    for edge_id in next_edges:
                        if np.allclose(self.edges_dict[edge_id]['seg_headings'], vals_rwy_dir['heading'], rtol=0, atol=1):
                            rwy_edges.append(edge_id)
                            rwy_node_id = edge_id[1]
                            rwy_nodes.append(rwy_node_id)
                            self.nodes_dict[rwy_node_id]['node_type'] = 'RWY_intersection'
                            self.nodes_dict[rwy_node_id]['node_name'] = rwy_dir
                            edge_now = edge_id
                        else:
                            ## obtain exit stopbars
                            exit_path = []
                            stopbar_nodeIDs = []
                            stopbar_names = []
                            is_RET = False
                            temp_edges = [edge_id]
                            while not stopbar_nodeIDs:
                                for temp_edge in temp_edges:
                                    if self.nodes_dict[temp_edge[1]]['node_type'] == 'Stopbar':
                                        # exit-specific info
                                        stopbar_nodeIDs.append(temp_edge[1])
                                        stopbar_names.append(self.nodes_dict[temp_edge[1]]['node_name'])
                                        is_RET = temp_edge[1] in vals['stopbars_RET']
                                        # rwy-specific info (over all exits)
                                        exit_path.append(temp_edge)
                                        stopbars_exits['node_ids'].add(temp_edge[1])
                                        stopbars_exits['edge_ids'].update(exit_path)
                                        # rwy-strip info (both directions)
                                        stopbars_io.add(temp_edge[1])
                                if len(temp_edges) == 1:
                                    exit_path.append(temp_edges[0])
                                    temp_edges = list(self.edges_dict[temp_edges[0]]['next_edges'])
                                else:
                                    break  # end search for stopbar-node if more than 1 possible next edge exists, since there should have been a stopbar until this point.
                            ## build dicts for exit-edges and entry-edges of reverse runway
                            if not stopbar_nodeIDs:
                                print('\n======================================================================================')
                                print('WARNING: no stopbar-nodeID found for exit-edge={} of RWY={}. Exit will not be added to RWY-data. While this does not impede routing, check xPlane-layout for errors.'.format(edge_id, rwy_dir))
                                print('======================================================================================\n')
                                continue
                            rwy_exitEdges[edge_id] = {'rwy_length':round(rwy_length, 1), 'RET':is_RET, 'stopbar_nodeIDs':stopbar_nodeIDs, 'stopbar_names':stopbar_names}
                            # get edge-IDs of reverse edge
                            edge_id_rev = (edge_id[1], edge_id[0])
                            rwy_rev_entryEdges[edge_id_rev] = {'rwy_length':round(rwy_length, 1), 'stopbar_nodeIDs':stopbar_nodeIDs, 'stopbar_names':stopbar_names}
                ## update dict of runway-direction
                vals_rwy_dir.update({'nodes':rwy_nodes, 'edges':rwy_edges, 'exits':rwy_exitEdges, 'stopbars_exits':stopbars_exits})
                ## insert gathered information into opposite runway-direction
                stopbars_rev_entryEdges = {(edge_id[1], edge_id[0]) for edge_id in stopbars_exits['edge_ids']}
                stopbars_rev_entries = {'node_ids':stopbars_exits['node_ids'], 'edge_ids':stopbars_rev_entryEdges}
                vals[vals['rwy_dirs'][idx-1]].update({'entries':rwy_rev_entryEdges, 'stopbars_entries':stopbars_rev_entries})  # add exits as entries to opposite rwy-direction
                ## store all edges that are part of RWY-exits
                edge_ids_exits.update(stopbars_exits['edge_ids'])
                edge_ids_entries.update(stopbars_rev_entryEdges)
                
            ## gather general runway-strip information
            rwy_nodes = set()
            rwy_nodes.update(vals[rwy_dir1]['nodes'])
            rwy_nodes.update(vals[rwy_dir2]['nodes'])
            rwy_edges = set()
            rwy_edges.update(vals[rwy_dir1]['edges'])
            rwy_edges.update(vals[rwy_dir2]['edges'])
            vals.update({'rwy_nodes':rwy_nodes, 'rwy_edges':rwy_edges})
            
            ## gather information about remaining stopbars that are not entries/exits, based on 1st runway-direction:
            stopbars_remaining = vals['stopbars'].difference(stopbars_io)
            ## crossings
            node_ids_crossing = set()
            edge_ids_crossing = set()
            if rwy_strip in edges_special_RWY['crossing']:
                node_ids_crossing = set()
                edge_ids_crossing.update(edges_special_RWY['crossing'][rwy_strip])
                for edge_id in edges_special_RWY['crossing'][rwy_strip]:
                    eids_to_check = set(self.edges_dict[edge_id]['next_edges'])
                    while eids_to_check:
                        eid_to_check = eids_to_check.pop()
                        edge_ids_crossing.update([eid_to_check, (eid_to_check[1], eid_to_check[0])])
                        node_end = self.nodes_dict[eid_to_check[1]]
                        if node_end['node_type'] != 'Stopbar':
                            eids_to_check.update(self.edges_dict[eid_to_check]['next_edges'])
                        else:
                            node_ids_crossing.add(eid_to_check[1])
                stopbars_remaining.difference_update(node_ids_crossing)
                edge_ids_crossing.difference_update(edge_ids_exits)
                edge_ids_crossing.difference_update(edge_ids_entries)
            stopbars_crossing = {'node_ids': node_ids_crossing, 'edge_ids': edge_ids_crossing}
            ## go-around ahead of RWY-direction1
            node_ids_ahead = set()
            edge_ids_ahead = set()
            if rwy_dir1 in edges_special_RWY['ahead']:
                node_ids_ahead = set()
                edge_ids_ahead.update(edges_special_RWY['ahead'][rwy_dir1])
                for edge_id in edges_special_RWY['ahead'][rwy_dir1]:
                    eids_to_check = set(self.edges_dict[edge_id]['next_edges'])
                    while eids_to_check:
                        eid_to_check = eids_to_check.pop()
                        edge_ids_ahead.update([eid_to_check, (eid_to_check[1], eid_to_check[0])])
                        node_end = self.nodes_dict[eid_to_check[1]]
                        if node_end['node_type'] != 'Stopbar':
                            eids_to_check.update(self.edges_dict[eid_to_check]['next_edges'])
                        else:
                            node_ids_ahead.add(eid_to_check[1])
                stopbars_remaining.difference_update(node_ids_ahead)
                edge_ids_ahead.difference_update(edge_ids_exits)
            stopbars_ahead = {'node_ids': node_ids_ahead, 'edge_ids': edge_ids_ahead}
            ## go-around ahead of RWY-direction2, i.e. behind RWY-direction1
            node_ids_behind = set()
            edge_ids_behind = set()
            if rwy_dir2 in edges_special_RWY['ahead']:
                node_ids_behind = set()
                edge_ids_behind.update(edges_special_RWY['ahead'][rwy_dir2])
                for edge_id in edges_special_RWY['ahead'][rwy_dir2]:
                    eids_to_check = set(self.edges_dict[edge_id]['next_edges'])
                    while eids_to_check:
                        eid_to_check = eids_to_check.pop()
                        edge_ids_behind.update([eid_to_check, (eid_to_check[1], eid_to_check[0])])
                        node_end = self.nodes_dict[eid_to_check[1]]
                        if node_end['node_type'] != 'Stopbar':
                            eids_to_check.update(self.edges_dict[eid_to_check]['next_edges'])
                        else:
                            node_ids_behind.add(eid_to_check[1])
                stopbars_remaining.difference_update(node_ids_behind)
                edge_ids_behind.difference_update(edge_ids_exits)
            stopbars_behind = {'node_ids': node_ids_behind, 'edge_ids': edge_ids_behind}
            assert not stopbars_remaining, 'remaining stopbars detected: this seems to be an unresolved case!'
            vals[rwy_dir1].update({'stopbars_crossings':stopbars_crossing, 'stopbars_ahead':stopbars_ahead, 'stopbars_behind':stopbars_behind})
            vals[rwy_dir2].update({'stopbars_crossings':stopbars_crossing, 'stopbars_ahead':stopbars_behind, 'stopbars_behind':stopbars_ahead})
        
        ## Add edge_type == rwy_edge to edge in edges dict
        rwy_edges_set = set()
        for rwy_name in self.runways_dict.keys():
            rwy_data = self.runways_dict[rwy_name]
            rwy_edges = rwy_data['rwy_edges']
            rwy_edges_set = rwy_edges_set | rwy_edges
        for rwy_edge in list(rwy_edges_set):
            self.edges_dict[rwy_edge]['edge_type'] = 'RWY_edge'
        
        print('Created runways_dict containing {} runway-strips\n'.format(len(self.runways_dict.keys())))
        
        
    
    #%% Create pushback and push-pull paths
    def create_pushpull_data(self):
        """
        Stores directional push-back and pull paths, obtained from SVG-edgeIDs.
        
        Contributors: @Jorick
        """
        t_start = time.perf_counter()
        ## PushBack Paths
        edges_pushback_dict = {}
        for ramp_id in self._svgEdges_pushback_dict.keys(): #loop over all ramps for which we have a pushback path
            if not ramp_id in edges_pushback_dict.keys(): # Create empty dict if gate does not exist in edges_pushback_dict yet
                edges_pushback_dict[ramp_id] = {'Standard': [], 'ICAO-A': [],'ICAO-B': [],'ICAO-C': [],'ICAO-D': [],'ICAO-E': [],'ICAO-F': []}
            ramp_node = self.ramp2node_dict[ramp_id]
            stand_edge_outgoing = self.ramp_dict[ramp_node]['edges_from_ramp'] #first edge of the push-back path
            assert len(stand_edge_outgoing) == 1, 'Multiple stand edges detected, this is weird. Maybe a taxi-in, taxi-out gate? Gate:{} Stand edges:{}'.format(ramp_id, stand_edge_outgoing)
            for sType in self._svgEdges_pushback_dict[ramp_id]: #loop over all types for which a pushback path is defined
                if len(self._svgEdges_pushback_dict[ramp_id][sType]) > 0:
                    pb_path_lst = [] #lst with the pushback path for this gate and this size, in order
                    pb_path_lst.append(stand_edge_outgoing[0])
                    pot_pb_edges = self._svgEdges_pushback_dict[ramp_id][sType]
                    
                    #Construct the pushback path from the (bidirectional edges) in the _svgEdges_pushback_dict                   
                    while pot_pb_edges:
                        last_node = pb_path_lst[-1][1] #last node of the last added edge to pushback path
                        # Find next pb edge
                        next_pb_edge = None
                        for pot_pb_edge in pot_pb_edges:
                            if pot_pb_edge[0] == last_node: #When the start of the pushback edge is the last node, we have found the next edge on the pushback path
                                next_pb_edge = pot_pb_edge
                                pb_path_lst.append(next_pb_edge)
                                break
                        if next_pb_edge is None:
                            break  # exit while-loop as PB-path is finished
                        # Remove next pb edge and the reverse of this edge from the potential pb edges
                        remove1 = pot_pb_edges.index(next_pb_edge)
                        pot_pb_edges.pop(remove1)
                        remove2 = pot_pb_edges.index((next_pb_edge[1], (next_pb_edge[0])))
                        pot_pb_edges.pop(remove2)
                    # add push back path for this gate and type
                    edges_pushback_dict[ramp_id][sType] = pb_path_lst
                    
        ## Pull paths
        edges_pull_dict = {}
        for ramp_id in self._svgEdges_pull_dict.keys(): #loop over all ramps for which we have a pull path
            if not ramp_id in edges_pull_dict.keys(): # Create empty dict if gate does not exist in edges_pull_dict yet
                edges_pull_dict[ramp_id] = {'Standard': [], 'ICAO-A': [],'ICAO-B': [],'ICAO-C': [],'ICAO-D': [],'ICAO-E': [],'ICAO-F': []}
            ramp_node = self.ramp2node_dict[ramp_id]
            for sType in self._svgEdges_pull_dict[ramp_id]: #loop over all types for which a pull path is defined
                if len(self._svgEdges_pull_dict[ramp_id][sType]) > 0:
                    if len(edges_pushback_dict[ramp_id][sType]) == 0: #if we don't have a special pb path for this sType, use the standard pb path
                        edges_pushback_dict[ramp_id][sType] = edges_pushback_dict[ramp_id]['Standard']
                    last_pushback_node = edges_pushback_dict[ramp_id][sType][-1][1] #last node of the last added edge to pushback path
                    pull_path_lst = [] #lst with the pull path for this gate and this size, in order
                    pot_pull_edges = self._svgEdges_pull_dict[ramp_id][sType]
                    
                    #Construct the pushpull path from the (bidirectional edges) in the _svgEdges_pull_dict     
                    last_node = last_pushback_node #start nodeof the pull path is the end node of pushback path
                    while pot_pull_edges:                        
                        # Find next pb edge
                        next_pull_edge = None
                        for pot_pull_edge in pot_pull_edges:
                            if pot_pull_edge[0] == last_node: #When the start of the pull is the last node, we have found the next edge onpull path
                                next_pull_edge = pot_pull_edge
                                pull_path_lst.append(next_pull_edge)
                                break
                        if next_pull_edge is None:
                            break  # exit while-loop as pull-path is finished
                        # Remove next pull edge and the reverse of this edge from the potential pull edges
                        remove1 = pot_pull_edges.index(next_pull_edge)
                        pot_pull_edges.pop(remove1)
                        remove2 = pot_pull_edges.index((next_pull_edge[1], (next_pull_edge[0])))
                        pot_pull_edges.pop(remove2)
                        last_node = pull_path_lst[-1][1] #last node of the last added edge to pull path
                    # add pull path for this gate and type
                    if len(pull_path_lst) != 0:
                        edges_pull_dict[ramp_id][sType] = pull_path_lst
        
        #Remove empty dicts in pull path and group paths in category groups
        pull_groups = {}
        for ramp_id in list(edges_pull_dict.keys()):
            last_cat = 'Standard'
            temp_lst = []
            groups = {}
            for sType in list(edges_pull_dict[ramp_id].keys()):
                if edges_pull_dict[ramp_id][sType] == []:
                    #edges_pull_dict[ramp_id].pop(sType)
                    if not sType == 'Standard':
                        temp_lst.append(sType)
                elif not sType == 'Standard':
                    groups[tuple(temp_lst)] = last_cat
                    temp_lst = [sType]
                    last_cat = sType
            groups[tuple(temp_lst)] = last_cat
            pull_groups[ramp_id] = groups
            if edges_pull_dict[ramp_id] == {}:
                edges_pull_dict.pop(ramp_id)
        
        #Remove empty dicts in push path and group paths in category groups
        push_groups = {}
        for ramp_id in list(edges_pushback_dict.keys()):
            last_cat = 'Standard'
            temp_lst = []
            groups = {}
            for sType in list(edges_pushback_dict[ramp_id].keys()):
                if edges_pushback_dict[ramp_id][sType] == []:
                    edges_pushback_dict[ramp_id].pop(sType)
                    if not sType == 'Standard':
                        temp_lst.append(sType)
                elif not sType == 'Standard':
                    groups[tuple(temp_lst)] = last_cat
                    temp_lst = [sType]
                    last_cat = sType
            groups[tuple(temp_lst)] = last_cat
            push_groups[ramp_id] = groups
            if edges_pushback_dict[ramp_id] == {}:
                edges_pushback_dict.pop(ramp_id)
        
        #Add push and pull paths to ramp dict
        for ramp_id in self.ramp2node_dict.keys():
            node_id = self.ramp2node_dict[ramp_id]
            if ramp_id in push_groups.keys():
                for sType_group in push_groups[ramp_id].keys():
                    self.ramp_dict[node_id]['pushback'][sType_group] = {}
                    self.ramp_dict[node_id]['pushback'][sType_group]['edges_push'] = edges_pushback_dict[ramp_id][push_groups[ramp_id][sType_group]]
                    if ramp_id in pull_groups.keys() and sType_group in pull_groups[ramp_id].keys() and edges_pull_dict[ramp_id][pull_groups[ramp_id][sType_group]] != []:
                        self.ramp_dict[node_id]['pushback'][sType_group]['edges_pull'] = edges_pull_dict[ramp_id][pull_groups[ramp_id][sType_group]]
                        self.ramp_dict[node_id]['pushback'][sType_group]['pb_type'] = 'push-pull'
                    else:
                        self.ramp_dict[node_id]['pushback'][sType_group]['pb_type'] = 'pushback'
               
        t_end = time.perf_counter()
        print('Pushback and push-pull paths construction finished. It took: {:.2f}sec\n'.format(t_end-t_start))
        
        # delete temporary dicts
        delattr(self, '_svgEdges_entries_dict')
        delattr(self, '_svgEdges_pushback_dict')
        delattr(self, '_svgEdges_pull_dict')
        
        
        
    #%% calculation functions
    def create_nx_graph(self):
        """
        Contributors: @Malte
        """
        import networkx as nx
        self.nx_graph = nx.DiGraph()  # if multiple lanes are ever needed: replace DiGraph() with MultiDiGraph()
        nodes_list = [(k,v) for k,v in self.nodes_dict.items()]
        edges_list = [(k[0],k[1],v) for k,v in self.edges_dict.items()]
        self.nx_graph.add_nodes_from(nodes_list)  # this adds all nodes with their dict-properties to the graph
        self.nx_graph.add_edges_from(edges_list)  # this adds all edges with their dict-properties to the graph
        if None in self.nx_graph.nodes:
            self.nx_graph.remove_node(None)  # otherwise, issues in plotting occur
        
        
        
    #%% convert functions: adapted from python-script "routing.py" from ENAC
    def convert_cautra2svg(self, x_cautra, y_cautra):
        matrix = self._cautra2svg
        x_svg = matrix[0] * x_cautra + matrix[1] * y_cautra + matrix[2]
        y_svg = matrix[3] * x_cautra + matrix[4] * y_cautra + matrix[5]
        return (x_svg, y_svg)

    def convert_svg2cautra(self, x_svg, y_svg):
        matrix = self._svg2cautra
        x_cautra = matrix[0] * x_svg + matrix[1] * y_svg + matrix[2]
        y_cautra = matrix[3] * x_svg + matrix[4] * y_svg + matrix[5]
        return (x_cautra, y_cautra)
    
    def convert_latlon2svg(self, lat, lon):
        matrix = self._latlon2svg
        x_svg = matrix[0] * lat + matrix[1] * lon + matrix[2]
        y_svg = matrix[3] * lat + matrix[4] * lon + matrix[5]
        return (x_svg, y_svg)
    
    def convert_svg2latlon(self, x_svg, y_svg):
        matrix = self._svg2latlon
        lat = matrix[0] * x_svg + matrix[1] * y_svg + matrix[2]
        lon = matrix[3] * x_svg + matrix[4] * y_svg + matrix[5]
        return (lat, lon)
    
    
    def check_conversion(self, node_id=None):
        """
        Tests for any issues when converting between latlon and SVG.
        
        Contributors: @Malte
        """
        ## get coordinates of one node
        if node_id is None:
            node_id = len(self.nodes_dict) // 2
        pos_latlon = self.nodes_dict[node_id]['pos_latlon']
        lat, lon = pos_latlon
        for _ in range(3):
            x, y = self.convert_latlon2svg(lat, lon)
            lat, lon = self.convert_svg2latlon(x, y)
            print(x, y)
        assert math.isclose(pos_latlon[0], lat, rel_tol=0, abs_tol=1e-6)
        assert math.isclose(pos_latlon[1], lon, rel_tol=0, abs_tol=1e-6)
        diff_latlon = math.sqrt((pos_latlon[0] - lat)**2 + (pos_latlon[1] - lon)**2)
        assert diff_latlon < 1e-6
        pos_xy = self.nodes_dict[node_id]['pos_xy']
        diff_svg = math.sqrt((pos_xy[0] - x)**2 + (pos_xy[1] - y)**2) *6  # factor *6 to get distance in [m]
        assert diff_svg < 10
        return diff_svg
