# -*- coding: utf-8 -*-
#
# Copyright 2025 Malte von der Burg
#
# SPDX-License-Identifier: Apache-2.0

"""
Creates a Layout class-instance, allowing to plot the airport layout or parts thereof.
The Layout is saved as a pickle-file for further use.

Contributors:
    - Malte von der Burg (@Malte)
"""


import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import pickle as pkl


if __name__ == '__main__':
    abspath = os.path.dirname(os.path.realpath(os.getcwd()))
    abspath = abspath.replace('\\', '/')  # normalize path
    sys.path.append(abspath)
## import Layout-module
from src.Layout.Layout import Layout



#%% load layout-files + create Layout
airport_id = 'TEST'
version = ''

folder = abspath + '/data/airport_layouts/' + airport_id
svg_path = folder + f'/{airport_id}{version}.svg'
info_path = folder + f'/{airport_id}_airport_information.xlsx'
## obtain info on runways + convert RWY-strings into set of such
df_rwys = pd.read_excel(info_path, sheet_name='Runways', na_filter=False, dtype=str, index_col='RWY strip')
for col in ['Stopbars', 'RETs', 'Tug decoupling', 'Outbound HPs']:
    col_vals = []
    for idx in df_rwys.index:
        s = df_rwys.loc[idx, col].replace(' ','')
        if s == '':
            col_vals.append(set())
        else:
            col_vals.append(set(s.split(',')))
    df_rwys[col] = col_vals
## obtain info on WTC, TWYs, remote holding points
df_WTC = pd.read_excel(info_path, sheet_name='RECAT-EU', index_col='Leader\Follower')
df_HPs = pd.read_excel(info_path, sheet_name='Remote HPs', index_col='HP name')
## make info_dict
info_dict = {'runways': df_rwys.to_dict(orient='index'),
             'WTC': df_WTC.to_dict(orient='index'),
             'HPs': df_HPs.to_dict(orient='index')}
## create Layout-instance
devMode = True  # enable development-mode: perform extra checks
layout = Layout(svg_path, info_dict, devMode)



#%% carry out custom layout-checks
## plot flagged points based on error_check
if hasattr(layout, 'node_ids_to_check'):
    layout.highlight_nodes(layout.node_ids_to_check)
    plt.gca().set_title('Check nodes that were flagged during layout-creation')



#%% save layout
path_save = folder  # use airport-folder to save Layout class-instance
if layout.version:
    filename = f'layout_{layout.airport_id}-{layout.version}.pkl'
else:
    filename = f'layout_{layout.airport_id}.pkl'
save = True
if os.path.isfile(path_save + '/' + filename):
    save = input('Overwrite Layout-instance "{}" in {}?\nPress "y"=yes or "n"=no.\n'.format(filename, path_save)).lower() == 'y'
if save:
    os.makedirs(path_save, exist_ok=True)
    with open(path_save + '/' + filename, 'wb') as f:
        pkl.dump(layout, f, protocol=pkl.HIGHEST_PROTOCOL)
    print(f'Layout class-instance saved as "{filename}" in {path_save}.')
