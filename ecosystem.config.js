module.exports = {
    apps : [
      {
        name: "eval_client",
        script: "sudo",
        args: ["-E", "python", "-u", "/home/xilinx/.external_comms/eval_client.py"],
        env: {
          PORT: process.env.PORT,
          SECRET_PASSWORD: process.env.SECRET_PASSWORD
        }
      },
      {
        name: "game_engine",
        script: "sudo",
        args: ["-E", "python", "-u", "/home/xilinx/.external_comms/game_engine.py"],
      },
      {
        name: "ai_server",
        script: "sudo",
        args: ["-E", "python", "-u", "/home/xilinx/.external_comms/ai_server.py"],
      }
    ]
  };
  