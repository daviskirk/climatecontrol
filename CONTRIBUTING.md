Contributions are always welcome!  

Writing new issues
------------------

If you are using climatecontrol and find a
bug, please write an issue including such things as:

* climatecontrol version (run `pip show climatecontrol` and look for the version)
* Python version 
* Current operating system + version (Linux / Windows / Mac) 

Development
-----------

If you find a bug and want to fix it yourself or want to implement a new
feature, there are a few tools that can help you do this:

First install the dev dependencies

```sh
pip install -e ".[dev]"
```

Now you can use the `invoke` command to run formatting, code checks and tests as needed:

```sh
invoke --list  # show available commands

Available tasks:

  all      Run format, check and test all in one command.
  check    Check the code is ok by running flake8, black, isort and mypy.
  format   Format the code to make it compatible with the `check` command.
  test     Run all tests using pytest.
```

During development, run these as needed.  The same checks run in CI so if they
pass, you should be ok.  For example you can run:

```sh
invoke all  # format, check and run tests
```
