# Setting up a local testing environment with VS Code

### Install dependencies
Inside the repo, set up a virtual environment and install dependencies from the command line:
* `python -m venv .venv`  
* `source .venv/bin/activate`
* `pip install -e .`
* `pip install pytest`
* `pip install mock`

### Create config files
Create a folder called `./vscode`.
Inside the folder, create a file called `launch.json` with the following settings:
```
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python Debugger: Current File",
            "type": "debugpy",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal"
        }
    ]
}
```
Create a file called `settings.json` with the following settings:
```
{
    "python.testing.unittestArgs": [
        "-v",
        "-s",
        "./tests",
        "-p",
        "test_*.py"
    ],
    "python.testing.pytestEnabled": false,
    "python.testing.unittestEnabled": true
}
```
### Run unit tests locally in VS Code
You should now be able to run the unit tests locally:

<img width="604" alt="image" src="https://github.com/user-attachments/assets/ea5c74c5-ee56-4fc3-83c8-73a00c9cab1e">

### Send metrics to the agent using dogstasd
Create a folder for testing, such as `testapp/main.py`. Create a file inside the folder with the following code:
```
from datadog import initialize, statsd
import time

options = {
    "statsd_host": "127.0.0.1",
    "statsd_port": 8125,
}

initialize(**options)


while(1):
  statsd.increment('example_metric.increment', tags=["environment:dev"])
  statsd.decrement('example_metric.decrement', tags=["environment:dev"])
  time.sleep(10)
```

[Install the Agent](https://github.com/DataDog/datadog-agent).

Run the Agent: `./bin/agent/agent run -c bin/agent/dist/datadog.yaml`

Inside the `main.py` file that you just created, run the debugger to send logs to the Agent.
