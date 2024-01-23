import json
import os
import random
from itertools import combinations, product
# import kivy
from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.properties import NumericProperty, BooleanProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.popup import Popup
# from kivy.uix.button import Button

# Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
# Config.set('graphics', 'width', '327')
# Config.set('graphics', 'height', '720')
# Config.set('graphics', 'resizable', False)

ROOT = os.path.dirname(os.path.realpath(__file__))
IMAGES = os.path.join(ROOT, 'images')
DATA = os.path.join(ROOT, 'data')
CARD_PATH = os.path.join(IMAGES, 'card_{}.png')
GAME_TIME = 180  # [seconds]
         
class Deck(list):   
    VALUES = [1, 2, 3]
    COLORS = ['red', 'green', 'purple']
    SHAPES = ['diamond', 'flag', 'oval']
    FILLS = ['solid', 'pattern', 'empty']
    
    def __init__(self) -> None:
        vals = self.new_deck()
        super().__init__(vals)
        self.shuffle()
        
    def new_deck(self):
        return [(i, *x) for i, x in enumerate(product(
            self.VALUES, self.COLORS, self.SHAPES, self.FILLS))]
        
    def shuffle(self):
        random.shuffle(self)
   
        
class Tile(ToggleButton):  
    MAX_SELECTED = 3
    idx = NumericProperty(0)
    traits = (None, None, None, None)
    selected = BooleanProperty(False)
    
    @property
    def card(self):
        return self.idx, *self.traits
    
    def become(self, card):
        self.idx, *self.traits = card
        self.update()
    
    def on_press(self):
        n_selected = sum(c.selected for c in self.parent.children)
        if self.selected or n_selected < self.MAX_SELECTED:
            self.selected = not self.selected
        self.update()
        
    def toggle(self):
        self.selected = not self.selected
        self.update()
        
    def update(self):
        self.background_normal = CARD_PATH.format(self.idx)
        self.background_down = CARD_PATH.format(self.idx)
        return

    def __repr__(self):
        return f"Card{self.traits}"
        

class MainApp(App):
    icon = os.path.join(DATA, 'icon.png')
    
    def build(self): 
        self.home_screen = HomeScreen(name='home')
        self.main_screen = ThreezScreen(name='main')
        self.game_over_screen = GameOverScreen(name='game_over')
        
        sm = ScreenManager()
        sm.add_widget(self.home_screen)
        sm.add_widget(self.main_screen)
        sm.add_widget(self.game_over_screen)
        sm.current = 'home'
        return sm
    
    
class HomeScreen(Screen):  
    def start_game(self):
        self.parent.current = "main"
        main_screen = self.parent.get_screen("main")
        main_screen.ids.threez_game.start_new_game()
    
    
class ThreezScreen(Screen):
    threez_game: object
    
    def to_game_over_screen(self):
        self.parent.current = "game_over"
    
class GameOverScreen(Screen): 
    score = NumericProperty(-1)
    
    def to_home_screen(self):
        self.parent.current = "home"
    
    def on_enter(self):
        main_screen = self.manager.get_screen("main")
        threez_game = main_screen.threez_game
        self.score = threez_game.score

  
        
class ThreezGame(BoxLayout):
    N = 12
    FALSE_ENTRY_PENALTY = 5
    HINT_PENALTY = 3
    score = NumericProperty(0)
    hiscore = NumericProperty(0)
    time = NumericProperty(GAME_TIME)
    
    forfeit_popup: object
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with open("set.json", 'r') as f:
            self.db = json.load(f)
        self.forfeit_popup = ForfeitPopup()
       
    @property  
    def selected(self):
        return [tile for tile in self.tiles if tile.selected]
    
    def draw(self):
        # if the deck ran out, shuffle discarded cards back in the deck
        if not self.deck:
            self.deck.extend(self.discard_pile)
            self.discard_pile = []
            self.deck.shuffle()     
        return self.deck.pop(0)

    def deselect_all(self):       
        for tile in self.selected:
            tile.toggle()
       
    def enter(self):
        if self.is_set(self.selected):
            # determine how many points this set is worth
            points = sum([list(c.traits) for c in self.selected], [])
            points = len(set(points))
            self.score += points
            self.replace_cards(self.selected)
        else:
            self.score -= self.FALSE_ENTRY_PENALTY
        self.deselect_all() 
        
    def game_over(self, *args):
        Clock.unschedule(self.update_timer)
        self.hiscore = max(self.score, self.hiscore)
        self.db['hiscore'] = self.hiscore
        with open('set.json', 'w') as file:
            json.dump(self.db, file, indent=4)
        self.forfeit_popup.dismiss()
        self.parent.to_game_over_screen()
    
    def hint(self):
        self.deselect_all()
        self.score -= self.HINT_PENALTY
        set = random.choice(self.sets_in_board())
        tile = random.choice(set)
        tile.toggle()  
        
    def replace_cards(self, cards: list[Tile]):
        for tile in cards:
            if None not in tile.card:
                self.discard_pile.append(tile.card)
            tile.become(self.draw())
        if not self.sets_in_board():
            # self.wipe()
            # self.replace_cards(self.tiles)
            self.replace_cards(cards)
        
    def start_new_game(self):
        self.score = 0
        self.hiscore = self.db.get('hiscore', -1)
        self.time = GAME_TIME
        self.deck = Deck()
        self.discard_pile = []
        self.tiles: list[Tile] = self.ids.field.children
        self.replace_cards(self.tiles)
            
        self.deselect_all()
        Clock.schedule_interval(self.update_timer, 1)
          
    def is_set(self, cards) -> bool:
        """Do the selected cards form a set?"""
        if len(cards) != 3: return False
        triplets = zip(*[c.traits for c in cards])
        return all(len(set(t)) in (1, 3) for t in triplets)
            
    def sets_in_board(self):
        """List all the sets that can be made on current board"""
        return [abc for abc in combinations(self.tiles, 3) if self.is_set(abc)]

    def update_board(self):
        for tile in self.tiles:
            tile.update()

    def update_timer(self, dt):
        self.time -= dt
        if self.time < 0:
            self.game_over()
            
            
class ForfeitPopup(Popup): pass
            
            

if __name__ == '__main__':
    MainApp().run()