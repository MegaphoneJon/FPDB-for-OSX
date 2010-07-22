#!/usr/bin/python
# -*- coding: utf-8 -*-

#Copyright 2010 Steffen Schaumburg
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU Affero General Public License as published by
#the Free Software Foundation, version 3 of the License.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU Affero General Public License
#along with this program. If not, see <http://www.gnu.org/licenses/>.
#In the "official" distribution you can find the license in agpl-3.0.txt.

import threading
import pygtk
pygtk.require('2.0')
import gtk
import gobject
#import os
#import sys
#from optparse import OptionParser
from time import gmtime, mktime, strftime, strptime
#import pokereval

import logging #logging has been set up in fpdb.py or HUD_main.py, use their settings:
log = logging.getLogger("filter")


#import Configuration
#import Database
#import SQL
import Charset
import Filters

class TourneyFilters(Filters.Filters):
    def __init__(self, db, config, qdict, display = {}, debug=True):
        self.debug = debug
        self.db = db
        self.cursor = db.cursor
        self.sql = db.sql
        self.conf = db.config
        self.display = display
        
        self.filterText = {'playerstitle':'Hero:', 'sitestitle':'Sites:', 'seatstitle':'Number of Players:',
                    'seatsbetween':'Between:', 'seatsand':'And:', 'datestitle':'Date:',
                    'tourneyTypesTitle':'Tourney Type'}
        
        gen = self.conf.get_general_params()
        self.day_start = 0
        if 'day_start' in gen:
            self.day_start = float(gen['day_start'])

        # Outer Packing box
        self.mainVBox = gtk.VBox(False, 0)

        self.label = {}
        self.callback = {}

        self.make_filter()
    #end def __init__
    
    def __calendar_dialog(self, widget, entry):
        d = gtk.Window(gtk.WINDOW_TOPLEVEL)
        d.set_title('Pick a date')

        vb = gtk.VBox()
        cal = gtk.Calendar()
        vb.pack_start(cal, expand=False, padding=0)

        btn = gtk.Button('Done')
        btn.connect('clicked', self.__get_date, cal, entry, d)

        vb.pack_start(btn, expand=False, padding=4)

        d.add(vb)
        d.set_position(gtk.WIN_POS_MOUSE)
        d.show_all()
    #end def __calendar_dialog

    def __clear_dates(self, w):
        self.start_date.set_text('')
        self.end_date.set_text('')
    #end def __clear_dates

    def __get_dates(self):
        # self.day_start gives user's start of day in hours
        offset = int(self.day_start * 3600)   # calc day_start in seconds

        t1 = self.start_date.get_text()
        t2 = self.end_date.get_text()

        if t1 == '':
            t1 = '1970-01-02'
        if t2 == '':
            t2 = '2020-12-12'

        s1 = strptime(t1, "%Y-%m-%d") # make time_struct
        s2 = strptime(t2, "%Y-%m-%d")
        e1 = mktime(s1) + offset  # s1 is localtime, but returned time since epoch is UTC, then add the 
        e2 = mktime(s2) + offset  # s2 is localtime, but returned time since epoch is UTC
        e2 = e2 + 24 * 3600 - 1   # date test is inclusive, so add 23h 59m 59s to e2

        adj_t1 = strftime("%Y-%m-%d %H:%M:%S", gmtime(e1)) # make adjusted string including time
        adj_t2 = strftime("%Y-%m-%d %H:%M:%S", gmtime(e2))
        log.info("t1="+t1+" adj_t1="+adj_t1+'.')

        return (adj_t1, adj_t2)
    #end def __get_dates

    def __refresh(self, widget, entry):
        for w in self.mainVBox.get_children():
            w.destroy()
        self.make_filter()
    #end def __refresh

    def __set_hero_name(self, w, site):
        _name = w.get_text()
        # get_text() returns a str but we want internal variables to be unicode:
        _guiname = unicode(_name)
        self.heroes[site] = _guiname
        #log.debug("setting heroes[%s]: %s"%(site, self.heroes[site]))
    #end def __set_hero_name

    def __set_num_tourneys(self, w, val):
        try:
            self.numTourneys = int(w.get_text())
        except:
            self.numTourneys = 0
        print "setting numTourneys:", self.numTourneys
    #end def __set_num_tourneys

    def __set_seat_select(self, w, seat):
        #print "__set_seat_select: seat =", seat, "active =", w.get_active()
        self.seats[seat] = w.get_active()
        log.debug( "self.seats[%s] set to %s" %(seat, self.seats[seat]) )
    #end def __set_seat_select

    def __set_site_select(self, w, site):
        #print w.get_active()
        self.sites[site] = w.get_active()
        log.debug("self.sites[%s] set to %s" %(site, self.sites[site]))
    #end def __set_site_select

    def __set_tourney_type_select(self, w, tourneyType):
        #print w.get_active()
        self.tourneyTypes[tourneyType] = w.get_active()
        log.debug("self.tourney_types[%s] set to %s" %(tourneyType, self.tourneyTypes[tourneyType]))
    #end def __set_tourney_type_select

    def __toggle_box(self, widget, entry):
        if self.boxes[entry].props.visible:
            self.boxes[entry].hide()
            widget.set_label("show")
        else:
            self.boxes[entry].show()
            widget.set_label("hide")
    #end def __toggle_box

    def createPlayerLine(self, hbox, site, player):
        log.debug('add:"%s"' % player)
        label = gtk.Label(site +" id:")
        hbox.pack_start(label, False, False, 3)

        pname = gtk.Entry()
        pname.set_text(player)
        pname.set_width_chars(20)
        hbox.pack_start(pname, False, True, 0)
        #pname.connect("changed", self.__set_hero_name, site)

        # Added EntryCompletion but maybe comboBoxEntry is more flexible? (e.g. multiple choices)
        completion = gtk.EntryCompletion()
        pname.set_completion(completion)
        liststore = gtk.ListStore(gobject.TYPE_STRING)
        completion.set_model(liststore)
        completion.set_text_column(0)
        names = self.db.get_player_names(self.conf, self.siteid[site])  # (config=self.conf, site_id=None, like_player_name="%")
        for n in names: # list of single-element "tuples"
            _n = Charset.to_gui(n[0])
            _nt = (_n, )
            liststore.append(_nt)

        self.__set_hero_name(pname, site)
    #end def createPlayerLine
    
    def createSiteLine(self, hbox, site):
        cb = gtk.CheckButton(site)
        cb.connect('clicked', self.__set_site_select, site)
        cb.set_active(True)
        hbox.pack_start(cb, False, False, 0)
    #end def createSiteLine
    
    def createTourneyTypeLine(self, hbox, tourneyType):
        cb = gtk.CheckButton(str(tourneyType))
        cb.connect('clicked', self.__set_tourney_type_select, tourneyType)
        hbox.pack_start(cb, False, False, 0)
        cb.set_active(True)
    #end def createTourneyTypeLine

    def fillDateFrame(self, vbox):
        # Hat tip to Mika Bostrom - calendar code comes from PokerStats
        top_hbox = gtk.HBox(False, 0)
        vbox.pack_start(top_hbox, False, False, 0)
        lbl_title = gtk.Label(self.filterText['datestitle'])
        lbl_title.set_alignment(xalign=0.0, yalign=0.5)
        top_hbox.pack_start(lbl_title, expand=True, padding=3)
        showb = gtk.Button(label="hide", stock=None, use_underline=True)
        showb.set_alignment(xalign=1.0, yalign=0.5)
        showb.connect('clicked', self.__toggle_box, 'dates')
        top_hbox.pack_start(showb, expand=False, padding=1)

        vbox1 = gtk.VBox(False, 0)
        vbox.pack_start(vbox1, False, False, 0)
        self.boxes['dates'] = vbox1

        hbox = gtk.HBox()
        vbox1.pack_start(hbox, False, True, 0)

        lbl_start = gtk.Label('From:')

        btn_start = gtk.Button()
        btn_start.set_image(gtk.image_new_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_BUTTON))
        btn_start.connect('clicked', self.__calendar_dialog, self.start_date)

        hbox.pack_start(lbl_start, expand=False, padding=3)
        hbox.pack_start(btn_start, expand=False, padding=3)
        hbox.pack_start(self.start_date, expand=False, padding=2)

        #New row for end date
        hbox = gtk.HBox()
        vbox1.pack_start(hbox, False, True, 0)

        lbl_end = gtk.Label('  To:')
        btn_end = gtk.Button()
        btn_end.set_image(gtk.image_new_from_stock(gtk.STOCK_INDEX, gtk.ICON_SIZE_BUTTON))
        btn_end.connect('clicked', self.__calendar_dialog, self.end_date)

        btn_clear = gtk.Button(label=' Clear Dates ')
        btn_clear.connect('clicked', self.__clear_dates)

        hbox.pack_start(lbl_end, expand=False, padding=3)
        hbox.pack_start(btn_end, expand=False, padding=3)
        hbox.pack_start(self.end_date, expand=False, padding=2)

        hbox.pack_start(btn_clear, expand=False, padding=15)
    #end def fillDateFrame

    def fillPlayerFrame(self, vbox, display):
        top_hbox = gtk.HBox(False, 0)
        vbox.pack_start(top_hbox, False, False, 0)
        lbl_title = gtk.Label(self.filterText['playerstitle'])
        lbl_title.set_alignment(xalign=0.0, yalign=0.5)
        top_hbox.pack_start(lbl_title, expand=True, padding=3)
        showb = gtk.Button(label="refresh", stock=None, use_underline=True)
        showb.set_alignment(xalign=1.0, yalign=0.5)
        showb.connect('clicked', self.__refresh, 'players')

        vbox1 = gtk.VBox(False, 0)
        vbox.pack_start(vbox1, False, False, 0)
        self.boxes['players'] = vbox1

        for site in self.conf.get_supported_sites():
            hBox = gtk.HBox(False, 0)
            vbox1.pack_start(hBox, False, True, 0)

            player = self.conf.supported_sites[site].screen_name
            _pname = Charset.to_gui(player)
            self.createPlayerLine(hBox, site, _pname)
        
        hbox = gtk.HBox(False, 0)
        vbox1.pack_start(hbox, False, False, 0)
        #cb = gtk.CheckButton(self.filterText['groupsall'])
        #cb.connect('clicked', self.__set_group_select, 'allplayers')
        #hbox.pack_start(cb, False, False, 0)
        #self.sbGroups['allplayers'] = cb
        #self.groups['allplayers'] = False

        #lbl = gtk.Label('Min # Hands:')
        #lbl.set_alignment(xalign=1.0, yalign=0.5)
        #hbox.pack_start(lbl, expand=True, padding=3)

        #phands = gtk.Entry()
        #phands.set_text('0')
        #phands.set_width_chars(8)
        #hbox.pack_start(phands, False, False, 0)
        #phands.connect("changed", self.__set_num_hands, site)
        
        top_hbox.pack_start(showb, expand=False, padding=1)
    #end def fillPlayerFrame

    def fillSeatsFrame(self, vbox, display):
        hbox = gtk.HBox(False, 0)
        vbox.pack_start(hbox, False, False, 0)
        lbl_title = gtk.Label(self.filterText['seatstitle'])
        lbl_title.set_alignment(xalign=0.0, yalign=0.5)
        hbox.pack_start(lbl_title, expand=True, padding=3)
        showb = gtk.Button(label="hide", stock=None, use_underline=True)
        showb.set_alignment(xalign=1.0, yalign=0.5)
        showb.connect('clicked', self.__toggle_box, 'seats')
        hbox.pack_start(showb, expand=False, padding=1)

        vbox1 = gtk.VBox(False, 0)
        vbox.pack_start(vbox1, False, False, 0)
        self.boxes['seats'] = vbox1

        hbox = gtk.HBox(False, 0)
        vbox1.pack_start(hbox, False, True, 0)

        lbl_from = gtk.Label(self.filterText['seatsbetween'])
        lbl_to   = gtk.Label(self.filterText['seatsand'])
        adj1 = gtk.Adjustment(value=2, lower=2, upper=10, step_incr=1, page_incr=1, page_size=0)
        sb1 = gtk.SpinButton(adjustment=adj1, climb_rate=0.0, digits=0)
        adj2 = gtk.Adjustment(value=10, lower=2, upper=10, step_incr=1, page_incr=1, page_size=0)
        sb2 = gtk.SpinButton(adjustment=adj2, climb_rate=0.0, digits=0)

        hbox.pack_start(lbl_from, expand=False, padding=3)
        hbox.pack_start(sb1, False, False, 0)
        hbox.pack_start(lbl_to, expand=False, padding=3)
        hbox.pack_start(sb2, False, False, 0)

        self.sbSeats['from'] = sb1
        self.sbSeats['to']   = sb2
    #end def fillSeatsFrame

    def fillSitesFrame(self, vbox):
        top_hbox = gtk.HBox(False, 0)
        top_hbox.show()
        vbox.pack_start(top_hbox, False, False, 0)

        lbl_title = gtk.Label(self.filterText['sitestitle'])
        lbl_title.set_alignment(xalign=0.0, yalign=0.5)
        top_hbox.pack_start(lbl_title, expand=True, padding=3)

        showb = gtk.Button(label="hide", stock=None, use_underline=True)
        showb.set_alignment(xalign=1.0, yalign=0.5)
        showb.connect('clicked', self.__toggle_box, 'sites')
        showb.show()
        top_hbox.pack_start(showb, expand=False, padding=1)

        vbox1 = gtk.VBox(False, 0)
        self.boxes['sites'] = vbox1
        vbox.pack_start(vbox1, False, False, 0)

        for site in self.conf.get_supported_sites():
            hbox = gtk.HBox(False, 0)
            vbox1.pack_start(hbox, False, True, 0)
            self.createSiteLine(hbox, site)
    #end def fillSitesFrame

    def fillTourneyTypesFrame(self, vbox):
        top_hbox = gtk.HBox(False, 0)
        vbox.pack_start(top_hbox, False, False, 0)
        lbl_title = gtk.Label(self.filterText['tourneyTypesTitle'])
        lbl_title.set_alignment(xalign=0.0, yalign=0.5)
        top_hbox.pack_start(lbl_title, expand=True, padding=3)
        showb = gtk.Button(label="hide", stock=None, use_underline=True)
        showb.set_alignment(xalign=1.0, yalign=0.5)
        showb.connect('clicked', self.__toggle_box, 'tourneyTypes')
        top_hbox.pack_start(showb, expand=False, padding=1)

        vbox1 = gtk.VBox(False, 0)
        vbox.pack_start(vbox1, False, False, 0)
        self.boxes['tourneyTypes'] = vbox1

        result = self.db.getTourneyTypesIds()
        if len(result) >= 1:
            for line in result:
                hbox = gtk.HBox(False, 0)
                vbox1.pack_start(hbox, False, True, 0)
                self.createTourneyTypeLine(hbox, line[0])
        else:
            print "INFO: No tourney types returned from database"
            log.info("No tourney types returned from database")
    #end def fillTourneyTypesFrame

    def getDates(self):
        return self.__get_dates()
    #end def getDates

    def getHeroes(self):
        return self.heroes
    #end def getHeroes

    def getNumTourneys(self):
        return self.numTourneys
    #end def getNumTourneys

    def getSeats(self):
        if 'from' in self.sbSeats:
            self.seats['from'] = self.sbSeats['from'].get_value_as_int()
        if 'to' in self.sbSeats:
            self.seats['to'] = self.sbSeats['to'].get_value_as_int()
        return self.seats
    #end def getSeats

    def getSiteIds(self):
        return self.siteid
    #end def getSiteIds

    def getSites(self):
        return self.sites
    #end def getSites

    def getTourneyTypes(self):
        return self.tourneyTypes
    #end def getTourneyTypes

    def get_vbox(self):
        """returns the vbox of this thread"""
        return self.mainVBox
    #end def get_vbox

    def make_filter(self):
        self.tourneyTypes = {}
        #self.tourneys = {}
        self.sites = {}
        self.seats = {}
        self.siteid = {}
        self.heroes = {}
        self.boxes = {}

        for site in self.conf.get_supported_sites():
            #Get db site id for filtering later
            self.cursor.execute(self.sql.query['getSiteId'], (site,))
            result = self.db.cursor.fetchall()
            if len(result) == 1:
                self.siteid[site] = result[0][0]
            else:
                print "Either 0 or more than one site matched (%s) - EEK" % site

        # For use in date ranges.
        self.start_date = gtk.Entry(max=12)
        self.end_date = gtk.Entry(max=12)
        self.start_date.set_property('editable', False)
        self.end_date.set_property('editable', False)

        # For use in groups etc
        #self.sbGroups = {}
        self.numTourneys = 0

        playerFrame = gtk.Frame()
        playerFrame.set_label_align(0.0, 0.0)
        vbox = gtk.VBox(False, 0)

        self.fillPlayerFrame(vbox, self.display)
        playerFrame.add(vbox)

        sitesFrame = gtk.Frame()
        sitesFrame.set_label_align(0.0, 0.0)
        vbox = gtk.VBox(False, 0)

        self.fillSitesFrame(vbox)
        sitesFrame.add(vbox)

        # Tourney types
        tourneyTypesFrame = gtk.Frame()
        tourneyTypesFrame.set_label_align(0.0, 0.0)
        tourneyTypesFrame.show()
        vbox = gtk.VBox(False, 0)

        self.fillTourneyTypesFrame(vbox)
        tourneyTypesFrame.add(vbox)

        # Seats
        seatsFrame = gtk.Frame()
        seatsFrame.show()
        vbox = gtk.VBox(False, 0)
        self.sbSeats = {}

        self.fillSeatsFrame(vbox, self.display)
        seatsFrame.add(vbox)

        # Date
        dateFrame = gtk.Frame()
        dateFrame.set_label_align(0.0, 0.0)
        dateFrame.show()
        vbox = gtk.VBox(False, 0)

        self.fillDateFrame(vbox)
        dateFrame.add(vbox)

        # Buttons
        #self.Button1=gtk.Button("Unnamed 1")
        #self.Button1.set_sensitive(False)

        self.Button2=gtk.Button("Unnamed 2")
        self.Button2.set_sensitive(False)

        self.mainVBox.add(playerFrame)
        self.mainVBox.add(sitesFrame)
        self.mainVBox.add(seatsFrame)
        self.mainVBox.add(dateFrame)
        #self.mainVBox.add(self.Button1)
        self.mainVBox.add(self.Button2)

        self.mainVBox.show_all()

        # Should do this cleaner
        if "Heroes" not in self.display or self.display["Heroes"] == False:
            playerFrame.hide()
        if "Sites" not in self.display or self.display["Sites"] == False:
            sitesFrame.hide()
        if "Seats" not in self.display or self.display["Seats"] == False:
            seatsFrame.hide()
        if "Dates" not in self.display or self.display["Dates"] == False:
            dateFrame.hide()
        #if "Button1" not in self.display or self.display["Button1"] == False:
        #    self.Button1.hide()
        if "Button2" not in self.display or self.display["Button2"] == False:
            self.Button2.hide()

        #if 'button1' in self.label and self.label['button1']:
        #    self.Button1.set_label( self.label['button1'] )
        if 'button2' in self.label and self.label['button2']:
            self.Button2.set_label( self.label['button2'] )
        #if 'button1' in self.callback and self.callback['button1']:
        #    self.Button1.connect("clicked", self.callback['button1'], "clicked")
        #    self.Button1.set_sensitive(True)
        if 'button2' in self.callback and self.callback['button2']:
            self.Button2.connect("clicked", self.callback['button2'], "clicked")
            self.Button2.set_sensitive(True)

        # make sure any locks on db are released:
        self.db.rollback()
    #end def make_filter
    
    def registerButton2Name(self, title):
        self.Button2.set_label(title)
        self.label['button2'] = title
    #end def registerButton2Name

    def registerButton2Callback(self, callback):
        self.Button2.connect("clicked", callback, "clicked")
        self.Button2.set_sensitive(True)
        self.callback['button2'] = callback
    #end def registerButton2Callback
#end class TourneyFilters
