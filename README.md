# External-Comms

setup_reverse_proxy.sh is a script meant to be run on professors laptop to allow the connection of the eval_client with the eval_server. Dependencies needed is PM2 using npm and also all the python packages required in the game_engine, eval_client and ai_server python files.

ai_server.py is a script meant to consume IMU data of either leg or glove type and send to the game_engine the result of the prediction and also send the prediction confidences to the visualizer nodes for responsive feedback to the players.

eval_client.py is a script meant to consume game_state updates which are caused by player actions which need to be relayed to the eval_server and also receive the correct game_state from the eval_server to relay back to the game_engine in case the game_state we have is wrong (mostly due to wrong rain_bomb interactions)

game_engine.py is the monolithic game_engine which stores all player states for the entire game to be run. Contains values which need to be updated constantly such as the visibility status of opponents and other things such as the player profile_pictures which were custom made by us. All game updates such as damage information are also logged appropriately for easy debugging.

purge_queues.py is a script which is called from game_engine.py and eval_client.py as a safeguard to purge any data still left in the queues caused by players performing actions on their hardware before the evaluation had begun so that no wrong information will be sent/processed to the eval_server.