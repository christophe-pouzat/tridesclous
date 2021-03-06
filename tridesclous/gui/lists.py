import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np
import pandas as pd



class PeakModel(QtCore.QAbstractItemModel):
    def __init__(self, parent =None, spikesorter = None):
        QtCore.QAbstractItemModel.__init__(self,parent)
        self.spikesorter = spikesorter
        self.io = self.spikesorter.dataio
        
        if self.spikesorter.all_peaks is None:
            self.spikesorter.load_all_peaks()
        self.refresh_colors()
    
    
    def columnCount(self , parentIndex):
        return 4
        
    def rowCount(self, parentIndex):
        if not parentIndex.isValid():
            return self.spikesorter.all_peaks.shape[0]
        else :
            return 0
        
    def index(self, row, column, parentIndex):
        if not parentIndex.isValid():
            if column==0:
                childItem = row
            return self.createIndex(row, column, None)
        else:
            return QtCore.QModelIndex()
    
    def parent(self, index):
        return QtCore.QModelIndex()
    
    def data(self, index, role):
        if not index.isValid():
            return None
        
        if role ==QtCore.Qt.DisplayRole :
            col = index.column()
            row = index.row()
            ind = self.spikesorter.all_peaks.index[row]
            peak =  self.spikesorter.all_peaks.iloc[row, :]
            
            if col == 0:
                return '{}'.format(row)
            elif col == 1:
                return '{}'.format(int(ind[0]))
            elif col == 2:
                return '{:.4f}'.format(ind[1])
            elif col == 3:
                return '{}'.format(peak['label'])
            else:
                return None
        elif role == QtCore.Qt.DecorationRole :
            col = index.column()
            if col != 0: return None
            row = index.row()
            label = self.spikesorter.all_peaks.iloc[row, :]['label']
            if label in self.icons:
                return self.icons[label]
            else:
                return None
        else :
            return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable #| Qt.ItemIsDragEnabled

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return  ['num', 'seg_num', 'time', 'cluster_label'][section]
        return
    
    def refresh_colors(self):
        #TODO colors
        self.icons = { }
        #~ for k in np.unique(self.spikesorter.all_peaks['label']):
        for k in self.spikesorter.qcolors:
            color = self.spikesorter.qcolors.get(k, QtGui.QColor( 'white'))
            pix = QtGui.QPixmap(10,10 )
            pix.fill(color)
            self.icons[k] = QtGui.QIcon(pix)
        
        #~ self.icons[-1] = QIcon(':/user-trash.png')
        
        self.layoutChanged.emit()
        
        
class PeakList(QtGui.QWidget):
    
    peak_selection_changed = QtCore.pyqtSignal()
    
    def __init__(self, spikesorter = None, parent=None):
        QtGui.QWidget.__init__(self, parent)
        
        self.spikesorter = spikesorter
        self.dataio = self.spikesorter.dataio
        
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        
        self.layout.addWidget(QtGui.QLabel('<b>All spikes</b>') )
        
        self.tree = QtGui.QTreeView(minimumWidth = 100, uniformRowHeights = True,
                    selectionMode= QtGui.QAbstractItemView.ExtendedSelection, selectionBehavior = QtGui.QTreeView.SelectRows,
                    contextMenuPolicy = QtCore.Qt.CustomContextMenu,)
        
        self.layout.addWidget(self.tree)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        
        self.model = PeakModel(spikesorter = spikesorter)
        self.tree.setModel(self.model)
        self.tree.selectionModel().selectionChanged.connect(self.on_tree_selection)

        for i in range(self.model.columnCount(None)):
            self.tree.resizeColumnToContents(i)
        self.tree.setColumnWidth(0,80)
    
    def refresh(self):
        self.model.refresh_colors()
    
    def on_tree_selection(self):
        self.spikesorter.all_peaks.loc[:, 'selected'] = False
        for index in self.tree.selectedIndexes():
            if index.column() == 0: 
                ind = self.spikesorter.all_peaks.index[index.row()]
                self.spikesorter.all_peaks.loc[ind, 'selected'] = True
        self.peak_selection_changed.emit()

    def open_context_menu(self):
        pass
    
    def on_peak_selection_changed(self):
        self.tree.selectionModel().selectionChanged.disconnect(self.on_tree_selection)
        
        selected_peaks = self.spikesorter.all_peaks[self.spikesorter.all_peaks['selected']]
        if selected_peaks.shape[0]>100:#otherwise this is verry slow
            selected_peaks = selected_peaks.iloc[:10,:]
        rows = [self.spikesorter.all_peaks.index.get_loc(ind) for ind in selected_peaks.index]
        
        # change selection
        self.tree.selectionModel().clearSelection()
        flags = QtGui.QItemSelectionModel.Select #| QItemSelectionModel.Rows
        itemsSelection = QtGui.QItemSelection()
        for r in rows:
            for c in range(2):
                index = self.tree.model().index(r,c,QtCore.QModelIndex())
                ir = QtGui.QItemSelectionRange( index )
                itemsSelection.append(ir)
        self.tree.selectionModel().select(itemsSelection , flags)

        # set selection visible
        if len(rows)>=1:
            index = self.tree.model().index(rows[0],0,QtCore.QModelIndex())
            self.tree.scrollTo(index)

        self.tree.selectionModel().selectionChanged.connect(self.on_tree_selection)        



class ClusterList(QtGui.QWidget):
    
    peak_selection_changed = QtCore.pyqtSignal()
    
    def __init__(self, spikesorter = None, parent=None):
        QtGui.QWidget.__init__(self, parent)
        
        self.spikesorter = spikesorter
        self.dataio = self.spikesorter.dataio
        
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)

        self.table = QtGui.QTableWidget()
        self.layout.addWidget(self.table)
        self.table.itemChanged.connect(self.on_item_changed)
        
        self.refresh()

    def refresh(self):
        self.table.itemChanged.disconnect(self.on_item_changed)
        sps = self.spikesorter
        self.table.clear()
        labels = ['label', 'nb_peaks', 'show/hide' ]
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(labels)
        #~ self.table.setMinimumWidth(100)
        #~ self.table.setColumnWidth(0,60)
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        self.table.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        
        self.table.setRowCount(self.spikesorter.cluster_labels.size)
        
        for i, k in enumerate(self.spikesorter.cluster_labels):
            color = self.spikesorter.qcolors.get(k, QtGui.QColor( 'white'))
            pix = QtGui.QPixmap(10,10)
            pix.fill(color)
            icon = QtGui.QIcon(pix)
            
            name = '{}'.format(k)
            item = QtGui.QTableWidgetItem(name)
            item.setFlags(QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsSelectable)
            self.table.setItem(i,0, item)
            item.setIcon(icon)
            
            item = QtGui.QTableWidgetItem('{}'.format(self.spikesorter.cluster_count[k]))
            item.setFlags(QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsSelectable)
            self.table.setItem(i,1, item)
            
            item = QtGui.QTableWidgetItem('')
            item.setFlags(QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsSelectable|QtCore.Qt.ItemIsUserCheckable)
            #~ item.setCheckState({ False: QtCore.Qt.Unchecked, True : QtCore.Qt.Checked}[sps.active_cluster[c]])#TODO
            item.setCheckState({ False: QtCore.Qt.Unchecked, True : QtCore.Qt.Checked}[True])
            self.table.setItem(i,2, item)
            
        self.table.itemChanged.connect(self.on_item_changed)        
    
    def peak_selection_changed(self):
        self.refresh()
    
    def on_item_changed(self, item):
        if item.column() != 2: return
        sel = {QtCore.Qt.Unchecked : False, QtCore.Qt.Checked : True}[item.checkState()]
        k = self.spikesorter.cluster_labels[item.row()]
        #TODO : change visibility of one cluster
        #~ sps.active_cluster[c] = sel
        #~ self.clusters_activation_changed.emit()

    def open_context_menu(self):
        pass


