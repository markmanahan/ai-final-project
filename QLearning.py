from __future__ import print_function

from future import standard_library

standard_library.install_aliases()
from builtins import range
from builtins import object
import MalmoPython
import json
import logging
import os
import random
import sys
import time
import itertools
import math
from numpy import argmin

if sys.version_info[0] == 2:
    import Tkinter as tk
else:
    import tkinter as tk


class TabQAgent(object):
    """Tabular Q-learning agent for discrete state/action spaces."""

    def __init__(self):

        self.epsilon = 0.05  # exploration rate
        self.alpha = 0.2     # learning rate
        self.gamma = 0.8  # reward discount factor

        self.logger = logging.getLogger(__name__)
        if False:  # True if you want to see more information
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        self.logger.handlers = []
        self.logger.addHandler(logging.StreamHandler(sys.stdout))


        self.movementActions = ["move 0", "move 1", "move -1", "strafe 1", "strafe -1"]
        self.turnSpeed = ["turn 0","turn 0.5", "turn 1", "turn -0.5", "turn -1"]
        self.hotkeyChoice = ["hotbar.1 1", "hotbar.2 1"]
        self.mouseAction = ["", "attack 1", "use 1"]
        #self.directions = ["setYaw 0", "setYaw 30", "setYaw 60", "setYaw 90", "setYaw 120"]

        self.playerX = 0
        self.playerZ = 0
        self.playerYaw = 0
        self.playerLife = 20.0
        self.playerDrankPotion = 0 # 0 false 1 true

        self.enemyLife = 20.0


        self.actions = list(itertools.product(self.movementActions, self.turnSpeed, self.hotkeyChoice, self.mouseAction)) #total number of actions: 140
        self.actions2 = list(itertools.product(self.movementActions, self.turnSpeed, ["hotbar.1 1"], self.mouseAction))
        print("size of actions: ", len(self.actions2))
        self.q_table = {}
        self.canvas = None
        self.root = None
        
    ### Change q_table to reflect what we have learnt.
    # Inputs: reward - int, current_state - coordinate tuple, prev_state - coordinate tuple, prev_a - int
    # Output: updated q_table
    def updateQTable(self, reward, current_state, prev_state, prev_a):
        # Keeping a running average of all previously observed samples
        self.q_table[prev_state][prev_a] = (1 - self.alpha) * self.q_table[prev_state][prev_a] + self.alpha * (reward + (self.gamma * max(self.q_table[current_state][i] for i in range(len(self.actions)))))

        return
    ### Change q_table to reflect what we have learnt upon reaching the terminal state.
    # Input: reward - int, prev_state - coordinate tuple, prev_a - int
    # Output: updated q_table
    def updateQTableFromTerminatingState(self, reward, prev_state, prev_a):
        self.q_table[prev_state][prev_a] = reward
        return

    def act(self, world_state, agent_host, current_r, enemy_state):
        obs_text = world_state.observations[-1].text
        enemyOb = json.loads(enemy_state.observations[-1].text)
        obs = json.loads(obs_text)  # most recent observation
        self.logger.debug(obs)
        if not u'XPos' in obs or not u'ZPos' in obs:
            self.logger.error("Incomplete observation received: %s\n\n\n" % obs_text)
            return 0


        self.playerYaw = obs[u'Yaw']
        self.playerX = obs[u'XPos']
        self.playerZ = obs[u'ZPos']
        self.playerLife = obs[u'Life']
        healthHighorLow = 1
        enemyCanAttack = 0

        if u'Life' in obs:
            if obs[u'Life'] <= 12:
                healthHighorLow = 0

        #if u'IsAlive' in obs:
        #    print("is alive: ", obs[u'IsAlive'])

        if u'LineOfSight' in enemyOb:
            if(enemyOb[u'LineOfSight'][u'inRange'] and enemyOb[u'LineOfSight'][u'type'] == 'Player'):
                #print("player seen\n")
                enemyCanAttack = 1




        #current_s needs to be changed to include,
        canAttack = 0   # can only be 0 or 1
        distanceFromEnemy = 100
        angleFromEnemy = 0




        if u'LineOfSight' in obs:
            #print(obs[u'LineOfSight'])
            if(obs[u'LineOfSight'][u'inRange'] and obs[u'LineOfSight'][u'type'] == 'Enemy'):
                #print("in range\n")
                canAttack = 1
                #print("NOT IN RANGE\n\n\n\n")
        else:
            print("No line of sight")

        if u'entities' in obs:
            for e in obs[u'entities']:
                #print("deubg: ",e)
                if u'name' in e and e[u'name'] == 'Enemy':

                    #print("entity: ",)
                    distanceFromEnemy = int(math.sqrt((e["x"] - self.playerX)*(e["x"] - self.playerX) + (e["z"] - self.playerZ)*(e["z"] - self.playerZ)))
                    if(distanceFromEnemy > 5): #Cap off distance we don't care if they are farther apart
                        distanceFromEnemy = 5
                    yaw = -180 * math.atan2(e["x"] - self.playerX, e["z"] - self.playerZ) / math.pi
                    #print("My yaw: ", self.playerYaw, ", calc. yaw: ", yaw, ", Difference: ", yaw - self.playerYaw)
                    difference = yaw - self.playerYaw
                    while difference < -180:
                        difference += 360;
                    while difference > 180:
                        difference -= 360;
                    difference /= 180.0
                    #print("Final distance: ", difference)
                    vals = [0, 0.33, 0.66, 1, -0.33, -0.66, -1]
                    i = argmin([abs(difference - vals[j]) for j in range(7)])
                    angleFromEnemy = vals[i]
                    #print("Final angle: ", angleFromEnemy)

        else:
            print("p a n i c\n\n\n")
            print(obs)
        if(self.playerDrankPotion == 0 and obs[u'Hotbar_1_item'] == "glass_bottle"):
            print("player drank potion")
            self.playerDrankPotion = 1
            self.actions = self.actions2 # get rid of that hotkey as option


                                    # was: (int(obs[u'XPos']), int(obs[u'ZPos']))
        current_s = "%d:%d:%.1f:%d:%d:%d" % (canAttack, distanceFromEnemy, float(angleFromEnemy), self.playerDrankPotion, healthHighorLow, enemyCanAttack)
        print("State: ", current_s)
        #self.logger.debug("State: %s (x = %.2f, z = %.1f)" % (current_s, float(obs[u'XPos']), float(obs[u'ZPos'])))
        if current_s not in self.q_table:
            print("NEW STATE\n")
            self.q_table[current_s] = ([0] * len(self.actions))

        # update Q values
        if self.prev_s is not None and self.prev_a is not None:
            self.updateQTable(current_r, current_s, self.prev_s, self.prev_a)


        # select the next action (find a s.t. self.actions[a] == next action)
        if random.random() <= self.epsilon:
            next_action = random.choice(range(len(self.actions)))
        else:
            #print(self.q_table[current_s])
            maxExp = max(self.q_table[current_s])
            #print("max is ",maxExp)
            bestResults = []
            for i in range(len(self.actions)):
                if self.q_table[current_s][i] == maxExp:
                    bestResults.append(i)
            next_action = random.choice(bestResults)

            print(self.actions[next_action])



        # try to send the selected action to agent, only update prev_s if this succeeds
        agent_host.sendCommand(self.actions[next_action][0])
        agent_host.sendCommand(self.actions[next_action][1])
        agent_host.sendCommand(self.actions[next_action][2])
        if(self.actions[next_action][2] == "hotbar.1 1"):
            agent_host.sendCommand("hotbar.1 0")
        else:
            agent_host.sendCommand("hotbar.2 0")

        if(self.actions[next_action][3] == "attack 1"):
            agent_host.sendCommand("attack 0")
            agent_host.sendCommand("use 0")
        agent_host.sendCommand(self.actions[next_action][3])

        self.prev_s = current_s
        self.prev_a = next_action



        return current_r


    #TEMP Code for enemy from Reflex

    def enemyAgentMoveRand(self, agent):
        y = random.choice(self.movementActions)
        agent.sendCommand(y)
        agent.sendCommand("turn " + str(random.uniform(-1,1)))
        agent.sendCommand("attack 0")
        agent.sendCommand("attack 1")
    '''
    def moveRight(self, ah):
        ah.sendCommand("strafe 1")


    def moveLeft(self, ah):
        ah.sendCommand("strafe -1")


    def moveStraight(self, ah):
        ah.sendCommand("move 1")


    def moveBack(self, ah):
        ah.sendCommand("move -1")
    '''

    def run(self, agent_host0, agent_host1):
        """run the agent on the world"""

        total_reward = 0

        self.prev_s = None
        self.prev_a = None

        state1 = agent_host0.getWorldState()

        if state1.is_mission_running and state1.number_of_observations_since_last_state > 0:
            print("here!\n")
            msg = state1.observations[-1].text
            ob = json.loads(msg)
        elif state1.is_mission_running:
            state1 = agent_host1.peekWorldState()
            while state1.number_of_observations_since_last_state == 0:
                print("waiting..")
                time.sleep(1)

        if(ob['Name'] == 'Player'):
            player = agent_host0
            enemy = agent_host1
        else:
            player = agent_host1
            enemy = agent_host0

        #unrolled first_action
        current_r = 0
        while True:
            time.sleep(0.2)
            player_state = player.getWorldState()
            enemy_state = enemy.getWorldState()
            for error in player_state.errors:
                self.logger.error("Error: %s" % error.text)

            print("current_r ", current_r)
            if player_state.is_mission_running and len(player_state.observations) > 0 and not \
            player_state.observations[-1].text == "{}":
                total_reward += self.act(player_state, player, current_r, enemy_state)
                self.enemyAgentMoveRand(enemy)
                break
            if not player_state.is_mission_running:
                break


        while player_state.is_mission_running:
            current_r = 0


            # allow time to stabilise after action
            while True:
                time.sleep(0.2)
                player_state = player.peekWorldState()
                enemy_state = enemy.peekWorldState()
                if not player_state.is_mission_running:
                    break
                if player_state.number_of_observations_since_last_state > 0 and enemy_state.number_of_observations_since_last_state > 0:
                    player_state = player.getWorldState()
                    enemy_state = enemy.getWorldState()
                    for error in player_state.errors:
                        self.logger.error("Error: %s" % error.text)
                    enemyOb = json.loads((enemy_state).observations[-1].text)
                    playerOb = json.loads((player_state).observations[-1].text)

                    if u'Life' in enemyOb:

                        if enemyOb[u'Life'] < self.enemyLife:
                            current_r += (self.enemyLife - enemyOb[u'Life'])*20
                        self.enemyLife = enemyOb[u'Life']

                    if u'Life' in playerOb:
                        current_r += (playerOb[u'Life'] - self.playerLife)*5
                        #self.playerLife = playerOb[u'Life']
                    if u'LineOfSight' in playerOb:
                        if playerOb[u'LineOfSight'][u'type'] == 'Enemy':
                            current_r += 2 # Give points just for looking at enemy

                    current_r-=1
                    print("current_r: ",current_r)

                    if player_state.is_mission_running and len(player_state.observations) > 0 and not \
                    player_state.observations[-1].text == "{}":
                        total_reward += self.act(player_state, player, current_r, enemy_state)
                        self.enemyAgentMoveRand(enemy)
                        break
                else: #Seems to happen only when one of them has died... or issues
                    print("NO NEW OBS\n")

                    '''
                    if player_state.number_of_observations_since_last_state > 0:
                        print(player_state.observations[-1].text)
                    if enemy_state.number_of_observations_since_last_state > 0:
                        print(enemy_state.observations[-1].text)
                    '''
                    enemy.sendCommand("quit")
                    player.sendCommand("quit")
                    break



        #time.sleep(1)
        # process final reward
        print("Done Processing loop\n")
        #player_state = player.peekWorldState()
        #enemy_state = enemy.peekWorldState()
        #enemyOb = enemy_state.observations
        #playerOb = player_state.observations
        if(len(player_state.observations) == 0 and len(enemy_state.observations) > 0):
            print("player died\n")
            current_r -= 1000
        if(len(enemy_state.observations) == 0 and len(player_state.observations) > 0):
            print("enemy died\n")
            current_r += 1000

        '''
        if u'PlayersKilled' in playerOb:
            if(playerOb[u'PlayersKilled'] == 1):
                print("VICTORY\n")
                current_r += 1000
        if u'PlayersKilled' in enemyOb:
            if enemyOb[u'PlayersKilled'] == 1:
                print("DEFEAT\n")
                current_r -=1000
        '''

        total_reward += current_r

        # update Q values
        if self.prev_s is not None and self.prev_a is not None:
            self.updateQTableFromTerminatingState(current_r, self.prev_s, self.prev_a)


        return total_reward
