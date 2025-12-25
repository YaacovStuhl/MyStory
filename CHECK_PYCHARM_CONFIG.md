# How to Check PyCharm Run Configuration

## Steps to Verify Your Configuration

1. **Open Run Configurations**
   - Go to: `Run` → `Edit Configurations...`
   - Or click the dropdown next to the Run button (top right) → `Edit Configurations...`

2. **Check the Script Path**
   - ✅ **CORRECT**: Should end with `...\MyStory\MyStory\app.py`
   - ❌ **WRONG**: Should NOT point to:
     - `...\site-packages\...` (any file in Python's site-packages)
     - `...\flask_limiter\_extension.py`
     - `...\flask\app.py`
     - Any file that's not your `app.py`

3. **Check the Working Directory**
   - ✅ **CORRECT**: Should be `C:\xampp\htdocs\MyStory\MyStory`
   - ❌ **WRONG**: Should NOT be:
     - `C:\Python313\...` (Python installation directory)
     - `C:\xampp\htdocs\MyStory` (parent directory)
     - Any directory that's not where your `app.py` file is

4. **Check if "Module name" is set**
   - If "Module name" field has anything in it (like `flask_limiter._extension`), clear it
   - The "Script path" field should be used instead

## Quick Fix

If you see a configuration with a script path pointing to `site-packages` or `flask_limiter`:
1. **Delete that configuration** (select it and click the minus `-` button)
2. **Create a new one**:
   - Click `+` → `Python`
   - Set Script path to: `C:\xampp\htdocs\MyStory\MyStory\app.py`
   - Set Working directory to: `C:\xampp\htdocs\MyStory\MyStory`
   - Click OK

## Alternative: Right-Click Method

The easiest way to create a correct configuration:
1. In the Project Explorer (left sidebar), find `MyStory/app.py`
2. **Right-click** on `app.py`
3. Select **"Run 'app'"** or **"Debug 'app'"**
4. This automatically creates the correct configuration!

