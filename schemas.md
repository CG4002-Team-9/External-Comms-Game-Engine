# Message Schemas and Explanations

This document provides the schemas of all possible messages used in the system, along with detailed explanations of each field. These messages are integral to the communication between various components of the project, including the evaluation client and server, game engine, AI server, and nodes like the Bluetooth devices and visualizer phones.

---

## Table of Contents

1. [TCP Messages between Evaluation Client and Evaluation Server](#1-tcp-messages-between-evaluation-client-and-evaluation-server)
   - [Message from Evaluation Client to Evaluation Server](#message-from-evaluation-client-to-evaluation-server)
   - [Message from Evaluation Server to Evaluation Client](#message-from-evaluation-server-to-evaluation-client)
2. [Messages to `update_ge_queue`](#2-messages-to-update_ge_queue)
3. [Messages Published to `update_everyone_topic` (MQTT)](#3-messages-published-to-update_everyone_topic-mqtt)
4. [Messages to `ai_queue`](#4-messages-to-ai_queue)
5. [Messages Published to `update_eval_server_queue`](#5-messages-published-to-update_eval_server_queue)
6. [Messages Published by the AI Server to `update_ge_queue`](#6-messages-published-by-the-ai-server-to-update_ge_queue)
7. [Field Explanations](#7-field-explanations)
   - [Common Fields](#common-fields)
   - [Specific to AI Messages](#specific-to-ai-messages)
   - [Other Fields](#other-fields)
8. [Summary](#8-summary)

---

## 1. TCP Messages between Evaluation Client and Evaluation Server

### Message from Evaluation Client to Evaluation Server

#### Schema

```json
{
  "player_id": int,
  "action": str,
  "game_state": {
    "p1": {
      "hp": int,
      "bullets": int,
      "bombs": int,
      "shield_hp": int,
      "deaths": int,
      "shields": int
    },
    "p2": {
      "hp": int,
      "bullets": int,
      "bombs": int,
      "shield_hp": int,
      "deaths": int,
      "shields": int
    }
  }
}
```

#### Explanation

- **`player_id`**:  
  - **Type**: `int`  
  - **Description**: The unique identifier of the player sending the action. Typically `1` or `2`.

- **`action`**:  
  - **Type**: `str`  
  - **Description**: The action performed by the player. Possible values include `"gun"`, `"shield"`, `"bomb"`, `"reload"`, `"basket"`, `"soccer"`, `"volley"`, `"bowl"`, etc.

- **`game_state`**:  
  - **Type**: `object`  
  - **Description**: The current state of the game, including both players.

  - **`p1`** and **`p2`**:  
    - **Type**: `object`  
    - **Fields**:
      - **`hp`**:  
        - **Type**: `int`  
        - **Description**: Hit points of the player.
      - **`bullets`**:  
        - **Type**: `int`  
        - **Description**: Number of bullets the player has.
      - **`bombs`**:  
        - **Type**: `int`  
        - **Description**: Number of bombs the player has.
      - **`shield_hp`**:  
        - **Type**: `int`  
        - **Description**: Shield hit points of the player.
      - **`deaths`**:  
        - **Type**: `int`  
        - **Description**: Number of times the player has died.
      - **`shields`**:  
        - **Type**: `int`  
        - **Description**: Number of shields the player has.

### Message from Evaluation Server to Evaluation Client

#### Schema

```json
{
  "p1": {
    "hp": int,
    "bullets": int,
    "bombs": int,
    "shield_hp": int,
    "deaths": int,
    "shields": int
  },
  "p2": {
    "hp": int,
    "bullets": int,
    "bombs": int,
    "shield_hp": int,
    "deaths": int,
    "shields": int
  }
}
```

#### Explanation

- **`p1`** and **`p2`**:  
  - **Type**: `object`  
  - **Description**: Updated game state for player 1 and player 2, respectively. Fields are the same as described in the previous message.

---

## 2. Messages to `update_ge_queue`

These messages are sent to the `update_ge_queue` for the game engine to process updates on player states and actions.

### Schema

```json
{
  "action": bool,
  "player_id": int,
  "action_type": str,
  "game_state": {
    "p1": {
      "hp": int,
      "bullets": int,
      "bombs": int,
      "shield_hp": int,
      "deaths": int,
      "shields": int
    },
    "p2": {
      "hp": int,
      "bullets": int,
      "bombs": int,
      "shield_hp": int,
      "deaths": int,
      "shields": int
    }
  }
}
```

### Explanation

- **`action`**:  
  - **Type**: `bool`  
  - **Description**: Indicates whether this message contains an action to be processed.  
    - If `true`, the game engine calculates the new state based on the action, updates the game state, and sends relevant data to the evaluation server via `update_eval_server_queue`.
    - If `false`, the game engine only updates its internal state with the provided values.

- **`player_id`**:  
  - **Type**: `int`  
  - **Description**: The ID of the player performing the action.

- **`action_type`**:  
  - **Type**: `str`  
  - **Description**: The type of action performed by the player. Possible values are the same as those for `action` in previous messages.

- **`game_state`**:  
  - **Type**: `object`  
  - **Description**: The current state of the game, including both players. Fields are as previously described.

---

## 3. Messages Published to `update_everyone_topic` (MQTT)

These messages are sent to all nodes (e.g., Bluetooth nodes, visualizer phones) whenever the game engine processes an action and needs to update clients.

### Schema

```json
{
  "game_state": {
    "p1": { ... },
    "p2": { ... }
  },
  "action": str,
  "player_id": int
}
```

### Explanation

- **`game_state`**:  
  - **Type**: `object`  
  - **Description**: The updated game state after processing the action.

- **`action`**:  
  - **Type**: `str`  
  - **Description**: The action that was performed. Used by nodes to trigger appropriate animations or responses.

- **`player_id`**:  
  - **Type**: `int`  
  - **Description**: The ID of the player who performed the action.

---

## 4. Messages to `ai_queue`

These messages are sent to the `ai_queue` to be processed by the AI server.

### Schema

```json
{
  "length": int,
  "ax": [int],
  "ay": [int],
  "az": [int],
  "player_id": int
}
```

### Explanation

- **`length`**:  
  - **Type**: `int`  
  - **Description**: The number of data points in each of the acceleration arrays. Typically `40`.

- **`ax`, `ay`, `az`**:  
  - **Type**: `array of int`  
  - **Description**: Arrays containing acceleration data along the X, Y, and Z axes, respectively. Values range from `-32768` to `32767` (16-bit signed integers).

- **`player_id`**:  
  - **Type**: `int`  
  - **Description**: The ID of the player whose data is being sent.

---

## 5. Messages Published to `update_eval_server_queue`

These messages are sent whenever the game engine processes an action and needs to inform the evaluation server via the evaluation client.

### Schema

```json
{
  "player_id": int,
  "action": str,
  "game_state": {
    "p1": { ... },
    "p2": { ... }
  }
}
```

### Explanation

- **`player_id`**:  
  - **Type**: `int`  
  - **Description**: The ID of the player who performed the action.

- **`action`**:  
  - **Type**: `str`  
  - **Description**: The action performed by the player.

- **`game_state`**:  
  - **Type**: `object`  
  - **Description**: The updated game state after processing the action.

---

## 6. Messages Published by the AI Server to `update_ge_queue`

These messages are sent by the AI server when a predicted action has a confidence above a certain threshold.

### Schema

```json
{
  "action": true,
  "player_id": int,
  "action_type": str,
  "confidence": float
}
```

### Explanation

- **`action`**:  
  - **Type**: `bool`  
  - **Description**: Indicates that this message contains an action to be processed.

- **`player_id`**:  
  - **Type**: `int`  
  - **Description**: The ID of the player whose action was predicted.

- **`action_type`**:  
  - **Type**: `str`  
  - **Description**: The type of action predicted by the AI model.

- **`confidence`**:  
  - **Type**: `float`  
  - **Description**: The confidence level of the prediction, ranging from `0.0` to `1.0`.

---

## 7. Field Explanations

### Common Fields

- **`player_id`**:  
  - **Type**: `int`  
  - **Description**: The unique identifier for a player in the game. Possible values are typically `1` or `2`.

- **`action`**:  
  - **Type**:  
    - `str` in messages where it represents the action performed (e.g., `"gun"`, `"shield"`).
    - `bool` in messages where it indicates the presence of an action to be processed (`true` or `false`).

- **`action_type`**:  
  - **Type**: `str`  
  - **Description**: Specifies the type of action. Possible values include `"gun"`, `"shield"`, `"bomb"`, `"reload"`, `"basket"`, `"soccer"`, `"volley"`, `"bowl"`, etc.

- **`game_state`**:  
  - **Type**: `object`  
  - **Description**: Represents the current state of the game, including both players.

  - **Fields for each player (`p1`, `p2`)**:
    - **`hp`**:  
      - **Type**: `int`  
      - **Description**: Hit points of the player. Typically ranges from `0` to `100`.
    - **`bullets`**:  
      - **Type**: `int`  
      - **Description**: Number of bullets the player has.
    - **`bombs`**:  
      - **Type**: `int`  
      - **Description**: Number of bombs the player has.
    - **`shield_hp`**:  
      - **Type**: `int`  
      - **Description**: Shield hit points of the player.
    - **`deaths`**:  
      - **Type**: `int`  
      - **Description**: Number of times the player has died.
    - **`shields`**:  
      - **Type**: `int`  
      - **Description**: Number of shields the player has.

### Specific to AI Messages

- **`length`**:  
  - **Type**: `int`  
  - **Description**: Number of data points in the acceleration arrays (`ax`, `ay`, `az`).

- **`ax`, `ay`, `az`**:  
  - **Type**: `array of int`  
  - **Description**: Acceleration data along the X, Y, and Z axes. Each array should have a length equal to `length`.

- **`confidence`**:  
  - **Type**: `float`  
  - **Description**: Confidence level of the AI prediction, ranging from `0.0` (no confidence) to `1.0` (full confidence).

### Other Fields

- **`update`**:  
  - **Type**: `bool`  
  - **Description**: Indicates whether the message should trigger an update to the game state. Used in messages to `update_ge_queue`.

- **`timestamp`**:  
  - **Type**: `str` (ISO 8601 format)  
  - **Description**: Timestamp indicating when the message was generated or the action occurred.

- **`players`**:  
  - **Type**: `array of objects`  
  - **Description**: List of player information. Each object may contain:
    - **`player_id`**: `int`  
    - **`position`**: `int`  
    - **`score`**: `int`  
    - **`name`**: `str`  
    - **`team`**: `str`  
    - **`status`**: `str` (e.g., `"alive"`, `"dead"`)

---

## 8. Summary

This document outlines the schemas and explanations for all possible messages exchanged within the system. Adhering to these schemas ensures consistent communication between components such as the evaluation client and server, game engine, AI server, and various nodes (e.g., Bluetooth devices, visualizer phones).

By understanding the purpose and structure of each message type, developers and integrators can effectively implement and troubleshoot the system's communication protocols, leading to a robust and reliable application.

---

**Note**: It's essential to keep this document updated with any changes in the message structures or additional fields introduced during the development process. Consistency and clarity in message schemas are crucial for the seamless operation of the system.