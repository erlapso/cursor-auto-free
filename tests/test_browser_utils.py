import os
import sys
import pytest
import logging
from browser_utils import BrowserManager

# All necessary imports are already in the test file:
# No additional imports required since pytest, os, sys, logging and BrowserManager are already imported.
# (No additional imports are needed; using the ones already in the test file.)
# No additional imports needed.
def test_missing_extension_logs_warning(monkeypatch, caplog):
    """
    Test that when the extension folder is missing, BrowserManager logs a warning
    and still returns valid browser options.
    """
    # Backup the original os.path.exists function.
    original_exists = os.path.exists
    # Monkeypatch os.path.exists to simulate 'turnstilePatch' directory being absent.
    def fake_exists(path):
        if "turnstilePatch" in path:
            return False
        return original_exists(path)
    
    monkeypatch.setattr(os.path, "exists", fake_exists)
    
    manager = BrowserManager()
    
    # Capture the warning logs.
    with caplog.at_level(logging.WARNING):
        options = manager._get_browser_options()
    
    # Assert that a warning regarding the missing extension was logged.
    warnings = [record.message for record in caplog.records if record.levelno == logging.WARNING]
    assert any("插件不存在:" in message for message in warnings), "Warning for missing extension was not logged."
    
    # Optionally, verify that options is an instance of ChromiumOptions.
    # Import ChromiumOptions from DrissionPage for the isinstance check.
    from DrissionPage import ChromiumOptions
    assert isinstance(options, ChromiumOptions), "Returned options is not an instance of ChromiumOptions."
def test_get_browser_options_configuration(monkeypatch):
    """
    Test that _get_browser_options correctly configures browser options including setting user agent,
    proxy, headless mode and other preferences. This test forces a non-darwin (linux) platform and provides
    a fake ChromiumOptions to log method calls.
    """
    # Set environment variables for proxy and headless mode.
    monkeypatch.setenv("BROWSER_PROXY", "http://fakeproxy")
    monkeypatch.setenv("BROWSER_HEADLESS", "False")
    # Force a non-mac platform.
    monkeypatch.setattr(sys, "platform", "linux")
    # Monkeypatch os.path.exists to simulate that "turnstilePatch" exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    # Monkeypatch os.getcwd to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_dir")
    # Define a fake ChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    user_agent = "fake-agent"
    manager = BrowserManager()
    options = manager._get_browser_options(user_agent)
    # The expected sequence of calls:
    # 1. add_extension should be called with "/fake_dir/turnstilePatch"
    # 2. set_pref should disable credentials service
    # 3. set_argument with "--hide-crash-restore-bubble"
    # 4. set_proxy with "http://fakeproxy"
    # 5. auto_port to auto-set a free port
    # 6. set_user_agent with "fake-agent"
    # 7. headless method should be called with False (since BROWSER_HEADLESS was set to "False")
    expected_calls = [
        ("add_extension", "/fake_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("set_proxy", "http://fakeproxy"),
        ("auto_port",),
        ("set_user_agent", "fake-agent"),
        ("headless", False),
    ]
    assert options.calls == expected_calls, "ChromiumOptions methods were not called as expected."
def test_init_and_quit_browser(monkeypatch):
    """
    Test that init_browser successfully instantiates a fake browser using a fake Chromium,
    and verifies that BrowserManager.quit() correctly calls the browser's quit method.
    """
    # Define a fake Chromium class.
    class FakeChromium:
        def __init__(self, options):
            self.options = options
            self.quit_called = False
        def quit(self):
            self.quit_called = True
    # Monkeypatch Chromium in browser_utils to use FakeChromium.
    monkeypatch.setattr("browser_utils.Chromium", FakeChromium)
    # Create an instance of BrowserManager and initialize the fake browser with a test user agent.
    manager = BrowserManager()
    fake_user_agent = "test-agent"
    browser = manager.init_browser(fake_user_agent)
    
    # Assert that the returned browser is an instance of the FakeChromium.
    assert isinstance(browser, FakeChromium), "init_browser did not return an instance of FakeChromium."
    
    # Now call quit and verify that the FakeChromium.quit method was called.
    manager.quit()
    assert browser.quit_called, "BrowserManager.quit() did not call browser.quit() as expected."
def test_get_extension_path_with_meipass(monkeypatch):
    """
    Test that _get_extension_path returns the correct extension path when sys._MEIPASS is set,
    simulating a packaged PyInstaller environment.
    """
    # Set sys._MEIPASS by adding it to sys.__dict__ to simulate a PyInstaller environment.
    fake_meipass = "/fake_meipass_dir"
    monkeypatch.setitem(sys.__dict__, "_MEIPASS", fake_meipass)
    
    # Monkeypatch os.path.exists to simulate that only the expected extension path exists.
    def fake_exists(path):
        expected_path = os.path.join(fake_meipass, "turnstilePatch")
        if path == expected_path:
            return True
        return False
    monkeypatch.setattr(os.path, "exists", fake_exists)
    
    manager = BrowserManager()
    result_path = manager._get_extension_path()
    expected_path = os.path.join(fake_meipass, "turnstilePatch")
    assert result_path == expected_path, "Expected extension path from sys._MEIPASS when available."
def test_get_browser_options_darwin(monkeypatch):
    """
    Test that _get_browser_options properly adds Mac-specific arguments
    when sys.platform is 'darwin', ensuring that "--no-sandbox" and "--disable-gpu"
    are set in addition to the common configuration.
    """
    # Force sys.platform to 'darwin'
    monkeypatch.setattr(sys, "platform", "darwin")
    # Ensure headless environment variable is True (default)
    monkeypatch.setenv("BROWSER_HEADLESS", "True")
    # Monkeypatch os.getcwd to return a fixed directory
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_dir")
    # Monkeypatch os.path.exists to simulate that "turnstilePatch" exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    options = manager._get_browser_options()
    
    # The expected sequence of calls on Mac:
    # 1. add_extension: with "/fake_dir/turnstilePatch"
    # 2. set_pref: disable credentials service
    # 3. set_argument: "--hide-crash-restore-bubble"
    # 4. auto_port: to auto-set a port
    # 5. headless: with True (since BROWSER_HEADLESS is "True")
    # 6. set_argument: "--no-sandbox" for Mac-specific handling
    # 7. set_argument: "--disable-gpu" for Mac-specific handling
    expected_calls = [
        ("add_extension", "/fake_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", True),
        ("set_argument", "--no-sandbox"),
        ("set_argument", "--disable-gpu"),
    ]
    assert options.calls == expected_calls, "Mac-specific configuration was not applied as expected."
def test_quit_browser_handles_exception(monkeypatch):
    """
    Test that BrowserManager.quit() safely handles exceptions raised during browser.quit().
    This ensures that even if browser.quit() fails, BrowserManager.quit() doesn't propagate the error.
    """
    class FakeBrowser:
        def __init__(self):
            self.quit_called = False
        def quit(self):
            self.quit_called = True
            raise Exception("Fake quit exception")
    manager = BrowserManager()
    fake_browser = FakeBrowser()
    manager.browser = fake_browser
    # Calling quit should not raise an exception even if browser.quit() fails.
    try:
        manager.quit()
    except Exception:
        pytest.fail("BrowserManager.quit() should handle exceptions internally and not propagate them.")
    # Although the FakeBrowser.quit() raised an exception,
    # we can verify that it was still called.
    assert fake_browser.quit_called, "FakeBrowser.quit() was not called as expected."
def test_get_browser_options_defaults(monkeypatch):
    """
    Test that _get_browser_options returns browser options with default configuration
    when no user agent or proxy is provided in a non-darwin environment.
    This ensures that methods such as set_user_agent and set_proxy are not called.
    """
    # Remove any environment variables for proxy and headless mode.
    monkeypatch.delenv("BROWSER_PROXY", raising=False)
    monkeypatch.delenv("BROWSER_HEADLESS", raising=False)
    
    # Force sys.platform to a non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    
    # Monkeypatch os.getcwd to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_default")
    
    # Simulate that 'turnstilePatch' exists for the expected extension path.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    # Call _get_browser_options without specifying a user agent.
    options = manager._get_browser_options()
    
    # Expected calls in order:
    # 1. add_extension should be called with "/fake_default/turnstilePatch"
    # 2. set_pref to disable credentials_enable_service.
    # 3. set_argument for "--hide-crash-restore-bubble"
    # 4. auto_port
    # 5. headless with True (since default value from os.getenv is "True")
    expected_calls = [
        ("add_extension", "/fake_default/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Default browser options configuration does not match expected sequence."
def test_init_browser_user_agent_propagation(monkeypatch):
    """
    Test that init_browser correctly propagates the provided user agent to the
    _get_browser_options method and returns the dummy browser instance.
    This is done by monkeypatching _get_browser_options to record the user_agent parameter
    and also monkeypatching the Chromium class in browser_utils to avoid actual browser startup.
    """
    # Container to hold the user_agent value passed to _get_browser_options.
    captured_user_agent = []
    # Define a fake _get_browser_options that records the user_agent parameter and returns a dummy option.
    def fake_get_browser_options(self, user_agent=None):
        captured_user_agent.append(user_agent)
        return "dummy_options"
    # Monkeypatch BrowserManager._get_browser_options with our fake version.
    monkeypatch.setattr(BrowserManager, "_get_browser_options", fake_get_browser_options)
    
    # Monkeypatch Chromium in browser_utils so that it returns a dummy browser instance.
    monkeypatch.setattr("browser_utils.Chromium", lambda options: "dummy_browser_instance")
    
    # Instantiate BrowserManager and call init_browser with a test user agent.
    manager = BrowserManager()
    test_user_agent = "propagation-test-agent"
    browser = manager.init_browser(test_user_agent)
    
    # Assert that the captured user agent is the same as the one provided.
    assert captured_user_agent[0] == test_user_agent, "User agent was not propagated correctly to _get_browser_options."
    # Assert that the browser returned is the dummy instance from our monkeypatched Chromium.
    assert browser == "dummy_browser_instance", "init_browser did not return the expected dummy browser instance."
def test_quit_without_browser_quit_method():
    """
    Test that BrowserManager.quit() does not raise an error when the browser object
    does not have a 'quit' method. This simulates a scenario where an improperly
    initialized browser (or a dummy object) is assigned.
    """
    manager = BrowserManager()
    # Set browser to an object without a 'quit' method.
    manager.browser = object()
    # Calling quit should not raise an exception.
    try:
        manager.quit()
    except Exception as e:
        pytest.fail(f"BrowserManager.quit() raised an exception when browser has no quit method: {e}")
def test_get_extension_path_default(monkeypatch):
    """
    Test that _get_extension_path returns the local directory extension path
    when sys._MEIPASS is not set.
    """
    # Ensure sys does not have _MEIPASS attribute.
    monkeypatch.delattr(sys, '_MEIPASS', raising=False)
    
    # Set a fixed current working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/my_fake_dir")
    
    # Patch os.path.exists to return True only if the requested extension path exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if path == "/my_fake_dir/turnstilePatch" else original_exists(path))
    
    manager = BrowserManager()
    result = manager._get_extension_path()
    expected = "/my_fake_dir/turnstilePatch"
    assert result == expected, f"Expected extension path to be {expected}, got {result}"
def test_get_browser_options_defaults(monkeypatch):
    """
    Test that _get_browser_options returns browser options with default configuration
    when no user agent or proxy is provided in a non-darwin environment.
    This ensures that methods such as set_user_agent and set_proxy are not called.
    """
    # Remove any environment variables for proxy and headless mode.
    monkeypatch.delenv("BROWSER_PROXY", raising=False)
    monkeypatch.delenv("BROWSER_HEADLESS", raising=False)
    
    # Force sys.platform to a non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    
    # Monkeypatch os.getcwd to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_default")
    
    # Simulate that 'turnstilePatch' exists for the expected extension path.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    # Call _get_browser_options without specifying a user agent.
    options = manager._get_browser_options()
    
    # Expected calls in order:
    # 1. add_extension should be called with "/fake_default/turnstilePatch"
    # 2. set_pref to disable credentials_enable_service.
    # 3. set_argument for "--hide-crash-restore-bubble"
    # 4. auto_port
    # 5. headless with True (since default value from os.getenv is "True")
    expected_calls = [
        ("add_extension", "/fake_default/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Default browser options configuration does not match expected sequence."
def test_get_extension_path_raises_exception(monkeypatch):
    """
    Test that _get_extension_path raises FileNotFoundError when the extension folder is not found.
    This simulates an environment where neither sys._MEIPASS is set nor a local 'turnstilePatch' folder exists.
    """
    # Ensure sys._MEIPASS is not set.
    monkeypatch.delattr(sys, '_MEIPASS', raising=False)
    # Set os.getcwd() to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/missing_dir")
    # Monkeypatch os.path.exists to always return False for the extension path.
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    
    manager = BrowserManager()
    expected_error = "插件不存在: /missing_dir/turnstilePatch"
    with pytest.raises(FileNotFoundError, match=expected_error):
        manager._get_extension_path()
def test_get_browser_options_add_extension_exception(monkeypatch):
    """
    Test that _get_browser_options propagates an exception raised by add_extension
    if it is not a FileNotFoundError. This ensures that only FileNotFoundError exceptions are caught.
    """
    # Monkeypatch os.getcwd to return a fixed directory so that _get_extension_path returns a valid path.
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_extension_dir")
    # Simulate that the 'turnstilePatch' folder exists.
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else False)
    
    # Define a FakeChromiumOptions that raises a ValueError when add_extension is called.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            raise ValueError("Test exception")
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    
    # Expect that calling _get_browser_options propagates the ValueError raised in add_extension.
    with pytest.raises(ValueError, match="Test exception"):
        manager._get_browser_options()
def test_get_extension_path_with_meipass_missing(monkeypatch):
    """
    Test that _get_extension_path raises FileNotFoundError when sys._MEIPASS is set but 
    the expected extension directory under it is missing.
    """
    # Set a fake _MEIPASS to simulate a PyInstaller environment.
    fake_meipass = "/fake_meipass_missing"
    monkeypatch.setitem(sys.__dict__, "_MEIPASS", fake_meipass)
    
    # Monkeypatch os.path.exists to return False when checking for the expected extension path.
    original_exists = os.path.exists
    def fake_exists(path):
        if path == os.path.join(fake_meipass, "turnstilePatch"):
            return False
        return original_exists(path)
    monkeypatch.setattr(os.path, "exists", fake_exists)
    
    manager = BrowserManager()
    expected_path = os.path.join(fake_meipass, "turnstilePatch")
    with pytest.raises(FileNotFoundError, match=f"插件不存在: {expected_path}"):
        manager._get_extension_path()
def test_get_browser_options_empty_proxy(monkeypatch):
    """
    Test that when the BROWSER_PROXY environment variable is set to an empty string,
    _get_browser_options does not call set_proxy on the ChromiumOptions instance.
    """
    # Set BROWSER_PROXY environment variable to an empty string.
    monkeypatch.setenv("BROWSER_PROXY", "")
    # Force a non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set a fixed current working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/empty_proxy_dir")
    # Patch os.path.exists so that the extension folder exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    # Instantiate BrowserManager and get browser options without a user agent.
    manager = BrowserManager()
    options = manager._get_browser_options()
    
    # Ensure that set_proxy was not called.
    proxy_calls = [call for call in options.calls if call[0] == "set_proxy"]
    assert proxy_calls == [], "set_proxy should not be called when BROWSER_PROXY is an empty string."
    
    # Also check that add_extension, set_pref, set_argument, auto_port and headless are called as expected.
    expected_calls = [
        ("add_extension", "/empty_proxy_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", True),
    ]
    # Since no user agent is provided and we are on linux (so no Mac-specific flags),
    # the calls should match the expected sequence.
    assert options.calls == expected_calls, "Browser options configuration did not match the expected sequence when BROWSER_PROXY is empty."
def test_get_browser_options_darwin_non_headless(monkeypatch):
    """
    Test that _get_browser_options on a Darwin platform with BROWSER_HEADLESS set to "false"
    correctly configures the browser options to run in non-headless mode while also adding Mac‑specific arguments.
    """
    # Force Darwin platform.
    monkeypatch.setattr(sys, "platform", "darwin")
    # Set headless mode to false.
    monkeypatch.setenv("BROWSER_HEADLESS", "false")
    # Monkey-patch os.getcwd to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_darwin_dir")
    # Ensure that the extension folder exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkey-patch the ChromiumOptions in our module to use the fake version.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    options = manager._get_browser_options()
    
    # The expected method call order on Darwin with BROWSER_HEADLESS="false":
    expected_calls = [
        ("add_extension", "/fake_darwin_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", False),
        ("set_argument", "--no-sandbox"),
        ("set_argument", "--disable-gpu"),
    ]
    assert options.calls == expected_calls, "Darwin non-headless configuration was not applied as expected."
def test_get_browser_options_invalid_headless(monkeypatch):
    """
    Test that when BROWSER_HEADLESS is set to an invalid value (not 'true'),
    _get_browser_options interprets it as False (i.e. non-headless mode)
    and configures the options accordingly.
    """
    # Set BROWSER_HEADLESS to an invalid value.
    monkeypatch.setenv("BROWSER_HEADLESS", "nottrue")
    # Ensure no proxy is set.
    monkeypatch.delenv("BROWSER_PROXY", raising=False)
    # Force a non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set a fixed current working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_invalid_headless_dir")
    # Ensure that 'turnstilePatch' exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkey-patch BrowserUtils' ChromiumOptions to use our FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    # Create a BrowserManager instance and get the browser options with a test user agent.
    manager = BrowserManager()
    user_agent = "test-agent"
    options = manager._get_browser_options(user_agent)
    
    # Expected method calls:
    # 1. add_extension with "/fake_invalid_headless_dir/turnstilePatch"
    # 2. set_pref with "credentials_enable_service", False
    # 3. set_argument with "--hide-crash-restore-bubble"
    # 4. auto_port is called to find a free port
    # 5. set_user_agent with "test-agent"
    # 6. headless with False (since "nottrue" != "true")
    expected_calls = [
        ("add_extension", "/fake_invalid_headless_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", "test-agent"),
        ("headless", False),
    ]
    assert options.calls == expected_calls, "Invalid BROWSER_HEADLESS value did not result in correct headless configuration."
def test_quit_when_browser_is_none():
    """
    Test that calling BrowserManager.quit() does nothing and does not raise an exception
    when no browser has been initialized (i.e. manager.browser is None).
    """
    manager = BrowserManager()  # browser is not initialized so it should be None by default
    # Call quit() when no browser is present.
    try:
        manager.quit()
    except Exception as e:
        pytest.fail(f"BrowserManager.quit() raised an exception when browser is None: {e}")
    # Assert that manager.browser remains None after calling quit().
    assert manager.browser is None, "manager.browser should remain None after quit() when no browser was initialized."
def test_multiple_init_browser_reinitializes_browser(monkeypatch):
    """
    Test that calling init_browser multiple times reinitializes the browser.
    This ensures that the previous browser instance is replaced when init_browser is called again.
    """
    # Define a fake Chromium class that tracks initialization order.
    class FakeChromium:
        count = 0
        def __init__(self, options):
            FakeChromium.count += 1
            self.id = FakeChromium.count
        def quit(self):
            pass
    # Monkeypatch the Chromium class in browser_utils to use FakeChromium.
    monkeypatch.setattr("browser_utils.Chromium", FakeChromium)
    
    manager = BrowserManager()
    browser1 = manager.init_browser("agent1")
    browser2 = manager.init_browser("agent2")
    
    # Assert that the two initialized browsers have distinct ids.
    assert browser1.id != browser2.id, "init_browser did not reinitialize the browser."
    # Assert that the manager's browser attribute is updated to the second browser.
    assert manager.browser is browser2, "BrowserManager.browser was not updated after reinitializing."
def test_get_browser_options_missing_extension_with_user_agent(monkeypatch, caplog):
    """
    Test that when the extension folder is missing and a user agent is provided,
    _get_browser_options logs a warning and continues to configure the browser options correctly.
    """
    # Simulate missing extension folder: any path containing 'turnstilePatch' does not exist.
    original_exists = os.path.exists
    def fake_exists(path):
        if "turnstilePatch" in path:
            return False
        return original_exists(path)
    monkeypatch.setattr(os.path, "exists", fake_exists)
    
    # Set a fixed current working directory and force a non-darwin platform.
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_missing")
    monkeypatch.setattr(sys, "platform", "linux")
    
    # Define a fake ChromiumOptions that records calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    test_user_agent = "missing-agent"
    with caplog.at_level(logging.WARNING):
        options = manager._get_browser_options(test_user_agent)
    
    # Verify a warning was logged about the missing extension.
    warnings = [record.message for record in caplog.records if record.levelno == logging.WARNING]
    assert any("插件不存在:" in message for message in warnings), "Expected missing extension warning not logged."
    
    # Since the extension is missing, add_extension shouldn't have been recorded.
    # Expected sequence of calls:
    # 1. set_pref to disable credentials service,
    # 2. set_argument with "--hide-crash-restore-bubble",
    # 3. auto_port for free port,
    # 4. set_user_agent with the provided user agent, and
    # 5. headless is set (True by default as BROWSER_HEADLESS defaults to "True").
    expected_calls = [
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", test_user_agent),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Browser options call sequence does not match when extension is missing with user agent."
def test_get_browser_options_with_whitespace_proxy(monkeypatch):
    """
    Test that when the BROWSER_PROXY environment variable is set to a whitespace string,
    _get_browser_options still calls set_proxy with the whitespace value.
    """
    # Set BROWSER_PROXY to a whitespace string.
    monkeypatch.setenv("BROWSER_PROXY", " ")
    # Force a non-darwin platform.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set a fixed current working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/whitespace_proxy_dir")
    # Simulate that 'turnstilePatch' exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    # Initialize browser options without providing a user agent.
    options = manager._get_browser_options()
    
    # Check that set_proxy was called with " " (whitespace).
    proxy_calls = [call for call in options.calls if call[0] == "set_proxy" and call[1] == " "]
    assert proxy_calls, "set_proxy was not called with the whitespace proxy value."
    
    # Additionally, verify the other default calls are in place.
    expected_call_extension = ("add_extension", "/whitespace_proxy_dir/turnstilePatch")
    assert expected_call_extension in options.calls, "Extension was not added as expected."
    expected_call_pref = ("set_pref", "credentials_enable_service", False)
    assert expected_call_pref in options.calls, "Preference for credentials_enable_service was not set as expected."
    expected_call_argument = ("set_argument", "--hide-crash-restore-bubble")
    assert expected_call_argument in options.calls, "Argument '--hide-crash-restore-bubble' was not set as expected."
    expected_call_auto = ("auto_port",)
    assert expected_call_auto in options.calls, "auto_port was not called as expected."
    expected_call_headless = ("headless", True)
    assert expected_call_headless in options.calls, "headless mode was not set as expected."
def test_get_browser_options_mixed_case_headless(monkeypatch):
    """
    Test that _get_browser_options correctly interprets a mixed-case BROWSER_HEADLESS environment variable,
    ensuring that the headless mode is set to True even when the value is provided as "TrUe".
    """
    # Set BROWSER_HEADLESS to a mixed-case value.
    monkeypatch.setenv("BROWSER_HEADLESS", "TrUe")
    monkeypatch.delenv("BROWSER_PROXY", raising=False)
    # Force non-darwin (e.g. Linux) environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Patch os.getcwd to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/mixed_case_headless")
    # Monkey-patch os.path.exists to simulate that the extension folder exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    # Define a FakeChromiumOptions that logs method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    # Monkey-patch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    manager = BrowserManager()
    options = manager._get_browser_options("test-agent")
    expected_calls = [
        ("add_extension", "/mixed_case_headless/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", "test-agent"),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Mixed-case BROWSER_HEADLESS did not result in correct headless configuration."
def test_get_browser_options_missing_extension_no_add_extension(monkeypatch, caplog):
    """
    Test that when the extension folder is missing, _get_browser_options does not call add_extension,
    logs a warning, and still configures the remaining browser options correctly.
    """
    # Simulate missing extension folder by always returning False for paths containing "turnstilePatch"
    monkeypatch.setattr(os.path, "exists", lambda path: False if "turnstilePatch" in path else os.path.exists(path))
    monkeypatch.setattr(os, "getcwd", lambda: "/dummy_dir")
    monkeypatch.setattr(sys, "platform", "linux")
    
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkey-patch ChromiumOptions in browser_utils to use our fake class.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    test_agent = "dummy-agent"
    with caplog.at_level(logging.WARNING):
        options = manager._get_browser_options(test_agent)
    
    # Verify that a warning is logged due to missing extension folder.
    warnings = [record.message for record in caplog.records if record.levelno == logging.WARNING]
    assert any("插件不存在:" in message for message in warnings), "Warning for missing extension was not logged."
    
    # Verify that add_extension was not called.
    assert all(call[0] != "add_extension" for call in options.calls), "add_extension should not be called when extension folder is missing."
    
    # Verify that the remaining configuration calls are as expected.
    expected_calls = [
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", test_agent),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Browser options configuration did not match expected sequence when extension is missing."
def test_init_browser_without_user_agent(monkeypatch):
    """
    Test that init_browser, when called without a user agent, does not call
    set_user_agent on the browser options and correctly initializes the browser.
    """
    # Force a non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set a fixed current working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_no_agent")
    # Simulate that the 'turnstilePatch' folder exists.
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else False)
    # Define a fake ChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkey-patch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    # Define a fake Chromium that simply stores the provided options.
    class FakeChromium:
        def __init__(self, options):
            self.options = options
        def quit(self):
            pass
    
    # Monkey-patch Chromium in browser_utils to use FakeChromium.
    monkeypatch.setattr("browser_utils.Chromium", FakeChromium)
    
    manager = BrowserManager()
    # Call init_browser without passing a user agent.
    browser = manager.init_browser()
    
    # Assert that the returned browser is an instance of FakeChromium.
    assert isinstance(browser, FakeChromium), "init_browser did not return a FakeChromium instance."
    
    # Check the option calls and assert that set_user_agent was not called.
    option_calls = browser.options.calls
    user_agent_calls = [call for call in option_calls if call[0] == "set_user_agent"]
    assert user_agent_calls == [], "set_user_agent should not be called when no user agent is provided."
    
    # Verify that add_extension was called with the expected extension path.
    expected_extension_path = "/fake_no_agent/turnstilePatch"
    add_ext_calls = [call for call in option_calls if call == ("add_extension", expected_extension_path)]
    assert add_ext_calls, "add_extension was not called with the correct extension path."
def test_get_browser_options_windows(monkeypatch):
    """
    Test that _get_browser_options configures browser options correctly on a Windows (win32)
    platform without adding Mac-specific arguments, ensuring that the proxy, user agent,
    and headless mode are set based on the environment and provided parameters.
    """
    # Set environment variables for proxy and headless mode.
    monkeypatch.setenv("BROWSER_PROXY", "http://winproxy")
    monkeypatch.setenv("BROWSER_HEADLESS", "True")
    
    # Force the platform to "win32" to simulate a Windows environment.
    monkeypatch.setattr(sys, "platform", "win32")
    
    # Set os.getcwd() to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/win_dir")
    
    # Simulate that the 'turnstilePatch' folder exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a fake ChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkey-patch ChromiumOptions in browser_utils to use the FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    test_user_agent = "win-user-agent"
    manager = BrowserManager()
    options = manager._get_browser_options(test_user_agent)
    
    # Expected calls sequence for a Windows environment (win32):
    # 1. add_extension should be called with "/win_dir/turnstilePatch".
    # 2. set_pref should disable credentials service.
    # 3. set_argument should add "--hide-crash-restore-bubble".
    # 4. set_proxy should be called with "http://winproxy".
    # 5. auto_port should be called.
    # 6. set_user_agent should be called with "win-user-agent".
    # 7. headless mode should be set to True based on the environment variable.
    expected_calls = [
        ("add_extension", "/win_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("set_proxy", "http://winproxy"),
        ("auto_port",),
        ("set_user_agent", test_user_agent),
        ("headless", True),
    ]
    
    assert options.calls == expected_calls, "Windows platform configuration did not match expected sequence."
def test_get_browser_options_propagates_non_filenotfound_error(monkeypatch):
    """
    Test that _get_browser_options propagates exceptions other than FileNotFoundError.
    In this case, we simulate _get_extension_path raising a PermissionError, and verify
    that the error is not caught internally by _get_browser_options.
    """
    manager = BrowserManager()
    
    # Define a fake _get_extension_path that raises a PermissionError.
    def fake_get_extension_path():
        raise PermissionError("Access denied")
    
    # Monkey-patch _get_extension_path on the manager instance.
    monkeypatch.setattr(manager, "_get_extension_path", fake_get_extension_path)
    
    # Assert that calling _get_browser_options propagates the PermissionError.
    with pytest.raises(PermissionError, match="Access denied"):
        manager._get_browser_options()
def test_no_warning_when_extension_exists(monkeypatch, caplog):
    """
    Test that when the extension directory exists, _get_browser_options does not log a warning.
    It also verifies that the add_extension method is called with the correct extension path.
    """
    # Force a non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set os.getcwd to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/existing_extension")
    # Ensure that os.path.exists returns True for any path containing "turnstilePatch".
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a fake ChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
            
    # Monkeypatch ChromiumOptions in browser_utils to use the FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    
    # Clear caplog records.
    caplog.clear()
    # Call _get_browser_options without providing a user agent.
    options = manager._get_browser_options()
    
    # Verify that no warning was logged regarding the extension folder.
    warnings = [record.message for record in caplog.records if record.levelno == logging.WARNING]
    assert not any("插件不存在:" in message for message in warnings), "Unexpected warning logged when extension exists."
    
    # Verify that add_extension was called with the correct extension path.
    expected_extension_path = "/existing_extension/turnstilePatch"
    add_ext_calls = [call for call in options.calls if call[0] == "add_extension" and call[1] == expected_extension_path]
    assert add_ext_calls, "add_extension was not called with the correct extension path when the extension exists."
def test_get_browser_options_empty_headless(monkeypatch):
    """
    Test that when the BROWSER_HEADLESS environment variable is set to an empty string,
    _get_browser_options interprets it as False (non-headless mode) and configures the browser
    options accordingly.
    """
    # Set the environment variable for headless mode to an empty string and ensure BROWSER_PROXY is unset.
    monkeypatch.setenv("BROWSER_HEADLESS", "")
    monkeypatch.delenv("BROWSER_PROXY", raising=False)
    # Force a non-darwin (Linux) environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set a fixed working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/empty_headless")
    # Patch os.path.exists by saving the original function to avoid recursion.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a fake ChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Patch ChromiumOptions to use the fake version.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    # Instantiate BrowserManager and retrieve browser options.
    manager = BrowserManager()
    options = manager._get_browser_options()
    
    # Expected configuration: headless should be False because an empty string is not interpreted as "true".
    expected_calls = [
        ("add_extension", "/empty_headless/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", False),
    ]
    assert options.calls == expected_calls, "When BROWSER_HEADLESS is empty, headless mode should be set to False."
def test_init_browser_with_empty_user_agent(monkeypatch):
    """
    Test that when an empty string ("") is provided as the user agent,
    _get_browser_options does not call set_user_agent and configures the other options correctly.
    """
    # Force non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set os.getcwd to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/empty_agent_dir")
    # Monkeypatch os.path.exists so that the extension is considered to exist.
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else os.path.exists(path))
    # Ensure no proxy and headless environment variables are set.
    monkeypatch.delenv("BROWSER_PROXY", raising=False)
    monkeypatch.delenv("BROWSER_HEADLESS", raising=False)  # headless will default to "True"
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    # Pass an empty string ("") as the user agent.
    options = manager._get_browser_options("")
    
    # Verify that set_user_agent was not called since an empty string is falsy.
    user_agent_calls = [call for call in options.calls if call[0] == "set_user_agent"]
    assert user_agent_calls == [], "set_user_agent should not be called when user_agent is an empty string."
    
    # Expected call sequence. Notice that set_user_agent is omitted.
    expected_calls = [
        ("add_extension", "/empty_agent_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Browser options configuration did not match expected sequence when user_agent is empty."
def test_multiple_quit_calls(monkeypatch):
    """
    Test that calling BrowserManager.quit() multiple times calls the browser's quit method
    on each call and does not propagate any errors.
    """
    # Define a fake browser that counts how many times quit() is called.
    class FakeBrowser:
        def __init__(self):
            self.quit_count = 0
        def quit(self):
            self.quit_count += 1
    # Initialize BrowserManager and set its browser to our fake browser.
    manager = BrowserManager()
    fake_browser = FakeBrowser()
    manager.browser = fake_browser
    
    # Call quit() multiple times.
    manager.quit()
    manager.quit()
    
    # Assert that the fake browser's quit() method was called twice.
    assert fake_browser.quit_count == 2, "BrowserManager.quit() did not call browser.quit() on multiple invocations."
def test_init_browser_does_not_quit_existing_browser(monkeypatch):
    """
    Test that calling init_browser on a BrowserManager that already has an existing browser
    does not automatically call quit() on the current browser.
    """
    # Define a fake Chromium class to simulate a browser instance.
    class FakeChromium:
        def __init__(self, options):
            self.options = options
            self.quit_called = False
        def quit(self):
            self.quit_called = True
    # Monkeypatch the Chromium class in browser_utils so that init_browser uses FakeChromium.
    monkeypatch.setattr("browser_utils.Chromium", FakeChromium)
    
    # Create an instance of BrowserManager.
    manager = BrowserManager()
    
    # Manually set a fake existing browser instance.
    old_browser = FakeChromium("old_option")
    manager.browser = old_browser
    # Call init_browser to reinitialize the browser.
    new_browser = manager.init_browser("new_agent")
    
    # Verify that the old browser's quit() method was not automatically called.
    assert not old_browser.quit_called, "init_browser should not call quit() on the existing browser."
    
    # Verify that the new browser instance is returned and manager.browser is updated.
    assert new_browser != old_browser, "New browser instance should be different than the old one."
    assert manager.browser == new_browser, "BrowserManager.browser should be updated to the new browser instance."
def test_init_browser_with_chromium_error(monkeypatch):
    """
    Test that init_browser properly propagates exceptions raised during 
    the initialization of Chromium. This simulates an error during browser startup.
    """
    # Monkey-patch Chromium to always raise an exception when instantiated.
    def fake_chromium(options):
        raise Exception("Chromium init failed")
    monkeypatch.setattr("browser_utils.Chromium", fake_chromium)
    manager = BrowserManager()
    with pytest.raises(Exception, match="Chromium init failed"):
        manager.init_browser("any-agent")
def test_init_browser_missing_extension(monkeypatch, caplog):
    """
    Test that init_browser logs a warning when the extension folder is missing,
    but still returns a valid browser instance.
    This simulates the scenario where the extension directory does not exist.
    """
    # Simulate missing extension folder by making os.path.exists return False for any path containing 'turnstilePatch'
    original_exists = os.path.exists
    def fake_exists(path):
        if "turnstilePatch" in path:
            return False
        return original_exists(path)
    monkeypatch.setattr(os.path, "exists", fake_exists)
    
    # Set a fixed current working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/missing_ext_dir")
    
    # Define a fake ChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    # Define a fake Chromium that simply stores the provided options.
    class FakeChromium:
        def __init__(self, options):
            self.options = options
        def quit(self):
            pass
    monkeypatch.setattr("browser_utils.Chromium", FakeChromium)
    
    # Create an instance of BrowserManager and initialize the browser.
    manager = BrowserManager()
    with caplog.at_level(logging.WARNING):
        browser = manager.init_browser("dummy-agent")
    
    # Assert that a warning about the missing extension was logged.
    warning_logged = any("插件不存在:" in record.message for record in caplog.records)
    assert warning_logged, "Expected warning for missing extension was not logged."
    
    # Assert that the returned browser is an instance of FakeChromium.
    assert isinstance(browser, FakeChromium), "init_browser did not return a FakeChromium instance."
def test_quit_does_not_reset_browser_attribute(monkeypatch):
    """
    Test that calling BrowserManager.quit() does not reset the manager.browser attribute.
    The test creates a fake browser with a quit() method, assigns it to manager.browser,
    calls quit(), and then asserts that the fake browser's quit() method was called while
    manager.browser remains assigned to the same instance.
    """
    class FakeBrowser:
        def __init__(self):
            self.quit_called = False
        def quit(self):
            self.quit_called = True
    manager = BrowserManager()
    fake_browser = FakeBrowser()
    manager.browser = fake_browser
    manager.quit()
    
    # Check that the fake browser's quit() method was called.
    assert fake_browser.quit_called, "FakeBrowser.quit() should have been called."
    
    # Assert that the manager.browser attribute still references the same fake browser.
    assert manager.browser is fake_browser, "manager.browser should not be reset after calling quit()."
def test_get_browser_options_uses_meipass(monkeypatch):
    """
    Test that when sys._MEIPASS is set and the expected extension directory exists,
    _get_browser_options uses the extension path from sys._MEIPASS instead of the local directory.
    This confirms that the extension is loaded from the packaged environment.
    """
    # Setup a fake _MEIPASS value.
    fake_meipass = "/fake_meipass_valid"
    monkeypatch.setitem(sys.__dict__, "_MEIPASS", fake_meipass)
    
    # Force a non-darwin platform.
    monkeypatch.setattr(sys, "platform", "linux")
    
    # Set BROWSER_HEADLESS environment variable to "True" (default behavior).
    monkeypatch.setenv("BROWSER_HEADLESS", "True")
    
    # Override os.getcwd to a different directory than _MEIPASS to ensure _MEIPASS is used.
    monkeypatch.setattr(os, "getcwd", lambda: "/local_dir")
    
    # Ensure that the extension exists only when using the _MEIPASS path.
    def fake_exists(path):
        expected_path = os.path.join(fake_meipass, "turnstilePatch")
        return path == expected_path
    monkeypatch.setattr(os.path, "exists", fake_exists)
    
    # Define a fake ChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkey-patch ChromiumOptions in browser_utils to use our fake version.
    monkeyatch_path = "browser_utils.ChromiumOptions"
    monkeypatch.setattr(monkeyatch_path, FakeChromiumOptions)
    
    manager = BrowserManager()
    # Call _get_browser_options without specifying a user agent.
    options = manager._get_browser_options()
    
    expected_calls = [
        ("add_extension", f"{fake_meipass}/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Using sys._MEIPASS did not lead to the expected extension path and configuration."
def test_init_browser_with_whitespace_user_agent(monkeypatch):
    """
    Test that init_browser correctly handles a user agent consisting of a whitespace string.
    This test verifies that even though the string is whitespace, it is considered as a truthy value
    and is propagated to the browser options through set_user_agent.
    """
    # Force non-darwin environment and set fixed working directory.
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os, "getcwd", lambda: "/fake_ws_dir")
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    # Define a fake Chromium that stores the options.
    class FakeChromium:
        def __init__(self, options):
            self.options = options
        def quit(self):
            pass
    monkeypatch.setattr("browser_utils.Chromium", FakeChromium)
    
    manager = BrowserManager()
    user_agent = " "  # whitespace user agent
    browser = manager.init_browser(user_agent)
    
    # Assert that init_browser returns a FakeChromium instance with expected method calls.
    assert isinstance(browser, FakeChromium), "Browser instance is not a FakeChromium as expected."
    calls = browser.options.calls
    expected_calls = [
        ("add_extension", "/fake_ws_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", " "),
        ("headless", True),
    ]
    assert calls == expected_calls, "The browser options did not record the expected method calls when using a whitespace user agent."
def test_browser_manager_initial_state():
    """
    Test that a newly instantiated BrowserManager has no active browser (i.e. browser is initialized to None).
    This verifies the constructor's default state.
    """
    manager = BrowserManager()
    assert manager.browser is None, "Expected BrowserManager.browser to be None upon initialization"
def test_get_browser_options_non_standard_platform(monkeypatch):
    """
    Test that _get_browser_options configures browser options without adding platform-specific
    Mac arguments when sys.platform is set to a non-standard value (e.g. "android").
    This ensures that only the common configuration is applied.
    """
    # Force a non-Mac, non-Windows, non-Linux platform.
    monkeypatch.setattr(sys, "platform", "android")
    
    # Remove any proxy and headless environment variables (headless defaults to "True").
    monkeypatch.delenv("BROWSER_PROXY", raising=False)
    monkeypatch.delenv("BROWSER_HEADLESS", raising=False)
    
    # Monkeypatch os.getcwd to return a fixed directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/test_android")
    
    # Simulate that the extension folder exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a fake ChromiumOptions to record the calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    # Initialize BrowserManager and get browser options with a test user agent.
    manager = BrowserManager()
    options = manager._get_browser_options("android-agent")
    
    # Check that the call sequence is exactly as expected for a non-Mac platform.
    expected_calls = [
        ("add_extension", "/test_android/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", "android-agent"),
        ("headless", True),
    ]
    
    assert options.calls == expected_calls, "Non-standard platform configuration did not match the expected sequence."
def test_get_browser_options_headless_with_spaces(monkeypatch):
    """
    Test that when BROWSER_HEADLESS is set to a value with leading/trailing spaces (e.g. " True "),
    _get_browser_options correctly interprets it (by converting to lowercase without trimming) and
    thereby sets headless mode to False because " true " != "true".
    """
    # Set BROWSER_HEADLESS with spaces so that .lower() does not match exactly "true"
    monkeypatch.setenv("BROWSER_HEADLESS", " True ")
    # Force a non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set a fixed directory for os.getcwd.
    monkeypatch.setattr(os, "getcwd", lambda: "/headless_spaces")
    # Simulate that the extension folder exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions to record method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use FakeChromiumOptions.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    user_agent = "agent-with-spaces"
    options = manager._get_browser_options(user_agent)
    
    # Expected: the extension is added, preferences are set, user agent is provided,
    # and headless mode is set to False because " True ".lower() returns " true " (with spaces) != "true".
    expected_calls = [
        ("add_extension", "/headless_spaces/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", user_agent),
        ("headless", False),
    ]
    assert options.calls == expected_calls, "Headless mode should be set to False when extra spaces are present in BROWSER_HEADLESS."
def test_get_browser_options_proxy_zero(monkeypatch):
    """
    Test that when the BROWSER_PROXY environment variable is set to "0",
    _get_browser_options correctly calls set_proxy with the value "0".
    This ensures that even an edge-case proxy value like "0" (which is a non-empty string)
    is properly propagated to the browser options.
    """
    # Set the BROWSER_PROXY environment variable to "0" and headless to "True"
    monkeypatch.setenv("BROWSER_PROXY", "0")
    monkeypatch.setenv("BROWSER_HEADLESS", "True")
    # Force a non-darwin platform.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set a fixed current working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/zero_proxy_dir")
    # Simulate that the 'turnstilePatch' folder exists by patching os.path.exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a FakeChromiumOptions to record method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    
    manager = BrowserManager()
    user_agent = "custom-agent"
    options = manager._get_browser_options(user_agent)
    
    # Verify that set_proxy was called with "0"
    proxy_calls = [call for call in options.calls if call[0] == "set_proxy" and call[1] == "0"]
    assert proxy_calls, "Expected set_proxy to be called with '0' when BROWSER_PROXY is set to '0'."
    
    # Verify that other configuration calls occur correctly.
    expected_calls = [
        ("add_extension", "/zero_proxy_dir/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("set_proxy", "0"),
        ("auto_port",),
        ("set_user_agent", "custom-agent"),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Browser options configuration did not match the expected sequence when BROWSER_PROXY is '0'."
def test_get_extension_path_with_relative_working_directory(monkeypatch):
    """
    Test that _get_extension_path correctly returns the extension path when os.getcwd()
    returns a relative path. This ensures that the BrowserManager properly constructs
    the extension path regardless of whether the working directory is relative or absolute.
    """
    # Ensure that sys does not have a _MEIPASS attribute.
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    # Set os.getcwd() to return a relative path.
    monkeypatch.setattr(os, "getcwd", lambda: "relative_project")
    
    # Monkey-patch os.path.exists to return True when the relative extension path is checked.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True 
                        if path == os.path.join("relative_project", "turnstilePatch") 
                        else original_exists(path))
    
    manager = BrowserManager()
    result = manager._get_extension_path()
    expected = os.path.join("relative_project", "turnstilePatch")
    assert result == expected, f"Expected extension path to be {expected} for a relative working directory, got {result}"
def test_get_extension_path_with_empty_meipass(monkeypatch):
    """
    Test that _get_extension_path returns the relative path "turnstilePatch"
    when sys._MEIPASS is set to an empty string. This simulates an edge-case where
    the packaged environment variable is incorrectly set to an empty string.
    """
    # Set sys._MEIPASS to an empty string
    monkeypatch.setitem(sys.__dict__, "_MEIPASS", "")
    # Even though os.getcwd() might return something, since _MEIPASS is set,
    # the code will use it. Here we simulate getcwd() returning a directory, but
    # since _MEIPASS is an empty string, the extension path should be relative.
    monkeypatch.setattr(os, "getcwd", lambda: "/ignored_dir")
    # Fix: monkeypatch os.path.exists instead of os.exists.
    monkeypatch.setattr(os.path, "exists", lambda path: True if path == "turnstilePatch" else False)
    manager = BrowserManager()
    result = manager._get_extension_path()
    expected = "turnstilePatch"
    assert result == expected, f"Expected extension path to be '{expected}', but got '{result}'"
def test_multiple_get_browser_options_instances(monkeypatch):
    """
    Test that consecutive calls to _get_browser_options return different ChromiumOptions instances.
    The test verifies that when a user agent is provided in the second call, the configuration
    includes the user agent while the first call (with no user agent) does not include it.
    """
    # Force non-darwin environment.
    monkeypatch.setattr(sys, "platform", "linux")
    # Set a fixed current working directory.
    monkeypatch.setattr(os, "getcwd", lambda: "/test_multiple")
    # Ensure that the extension folder exists.
    original_exists = os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else original_exists(path))
    
    # Define a fake ChromiumOptions that records method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch ChromiumOptions in browser_utils to use our fake version.
    monkeyatch_path = "browser_utils.ChromiumOptions"
    monkeypatch.setattr(monkeyatch_path, FakeChromiumOptions)
    
    manager = BrowserManager()
    
    # First call without a user agent.
    options1 = manager._get_browser_options()
    # Second call with a user agent.
    options2 = manager._get_browser_options("agent-test")
    
    # Verify that the two options objects are distinct.
    assert options1 is not options2, "Expected distinct ChromiumOptions instances on consecutive calls."
    
    # Expected call sequence for options1.
    expected_calls1 = [
        ("add_extension", "/test_multiple/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("headless", True),
    ]
    # Expected call sequence for options2 (user agent added in addition).
    expected_calls2 = [
        ("add_extension", "/test_multiple/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", "agent-test"),
        ("headless", True),
    ]
    
    assert options1.calls == expected_calls1, "First _get_browser_options call (without user agent) did not configure options as expected."
    assert options2.calls == expected_calls2, "Second _get_browser_options call (with user agent) did not configure options as expected."
def test_get_browser_options_numeric_user_agent(monkeypatch):
    """
    Test that _get_browser_options correctly handles a numeric user agent.
    This verifies that a non-string user agent (e.g., an integer) is passed to set_user_agent without conversion.
    """
    # Force a linux environment and set a fixed current working directory.
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os, "getcwd", lambda: "/num_user_agent")
    # Simulate that the extension folder exists by patching os.path.exists
    monkeypatch.setattr(os.path, "exists", lambda path: True if "turnstilePatch" in path else False)
    
    # Define a fake ChromiumOptions to record method calls.
    class FakeChromiumOptions:
        def __init__(self):
            self.calls = []
        def add_extension(self, arg):
            self.calls.append(("add_extension", arg))
        def set_pref(self, key, value):
            self.calls.append(("set_pref", key, value))
        def set_argument(self, arg):
            self.calls.append(("set_argument", arg))
        def set_proxy(self, proxy):
            self.calls.append(("set_proxy", proxy))
        def auto_port(self):
            self.calls.append(("auto_port",))
        def set_user_agent(self, agent):
            self.calls.append(("set_user_agent", agent))
        def headless(self, is_headless):
            self.calls.append(("headless", is_headless))
    
    # Monkeypatch the ChromiumOptions class in our module to use the fake one.
    monkeypatch.setattr("browser_utils.ChromiumOptions", FakeChromiumOptions)
    # Ensure that BROWSER_HEADLESS is defined so that headless mode is evaluated.
    monkeypatch.setenv("BROWSER_HEADLESS", "True")
    # Remove BROWSER_PROXY so proxy is not set.
    monkeypatch.delenv("BROWSER_PROXY", raising=False)
    
    manager = BrowserManager()
    # Pass an integer as the user agent.
    options = manager._get_browser_options(1234)
    
    expected_calls = [
        ("add_extension", "/num_user_agent/turnstilePatch"),
        ("set_pref", "credentials_enable_service", False),
        ("set_argument", "--hide-crash-restore-bubble"),
        ("auto_port",),
        ("set_user_agent", 1234),
        ("headless", True),
    ]
    assert options.calls == expected_calls, "Numeric user agent should be passed to set_user_agent without conversion."
def test_get_extension_path_with_empty_getcwd(monkeypatch):
    """
    Test that _get_extension_path returns 'turnstilePatch' when os.getcwd()
    returns an empty string. This simulates a scenario where the current working
    directory is an empty string.
    """
    # Force os.getcwd() to return an empty string.
    monkeypatch.setattr(os, "getcwd", lambda: "")
    
    # Monkeypatch os.path.exists so that it returns True only for "turnstilePatch".
    monkeypatch.setattr(os.path, "exists", lambda path: True if path == "turnstilePatch" else False)
    
    # Ensure that sys does not have a _MEIPASS attribute.
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    
    manager = BrowserManager()
    result = manager._get_extension_path()
    expected = "turnstilePatch"
    assert result == expected, f"Expected extension path to be '{expected}', got '{result}'"
def test_get_extension_path_with_trailing_slash(monkeypatch):
    """
    Test that _get_extension_path correctly constructs the extension path when os.getcwd()
    returns a path with a trailing slash. This ensures that trailing slashes do not affect the join operation.
    """
    # Ensure that sys does not have a _MEIPASS attribute, so the local working directory is used.
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    
    # Set os.getcwd() to return a path with trailing slash.
    monkeypatch.setattr(os, "getcwd", lambda: "/fakedir/")
    
    # The expected extension path is "/fakedir/turnstilePatch" regardless of the trailing slash.
    expected_path = os.path.join("/fakedir/", "turnstilePatch")
    
    # Simulate that the extension directory exists only at the expected path.
    monkeypatch.setattr(os.path, "exists", lambda path: True if path == expected_path else False)
    
    manager = BrowserManager()
    result = manager._get_extension_path()
    assert result == expected_path, f"Expected extension path '{expected_path}', got '{result}'"