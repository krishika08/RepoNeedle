import tempfile
import subprocess
import sys
import os

def test_package_installation():
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")
        print("Creating isolated virtualenv at:", venv_dir)
        subprocess.check_call([sys.executable, "-m", "venv", "--system-site-packages", venv_dir])
        
        python_bin = os.path.join(venv_dir, "Scripts", "python.exe")
        wheel_file = os.path.abspath("dist/reponeedle-1.1.0-py3-none-any.whl")
        sdist_file = os.path.abspath("dist/reponeedle-1.1.0.tar.gz")

        print("Testing Wheel installation...")
        subprocess.check_call([
            python_bin, "-m", "pip", "install", "--no-index", "--no-deps", wheel_file
        ])

        # Test wheel imports and metadata
        test_script = (
            "import reponeedle\n"
            "print('VERSION:', reponeedle.__version__)\n"
            "from reponeedle import RepoNeedleEngine, RankerType, ChangeImpactRanker, ChangeImpactConfig\n"
            "assert reponeedle.__version__ == '1.1.0'\n"
            "assert RankerType.LEGACY == 'legacy'\n"
            "assert RankerType.CHANGE_IMPACT == 'change_impact'\n"
            "print('WHEEL IMPORT AND METADATA TESTS PASSED!')\n"
        )
        out = subprocess.check_output([python_bin, "-c", test_script], text=True)
        print(out)

        # Test sdist installation in a separate venv
        sdist_venv = os.path.join(tmpdir, "venv_sdist")
        print("Creating sdist virtualenv at:", sdist_venv)
        subprocess.check_call([sys.executable, "-m", "venv", "--system-site-packages", sdist_venv])
        python_sdist = os.path.join(sdist_venv, "Scripts", "python.exe")

        print("Testing SDist installation...")
        subprocess.check_call([
            python_sdist, "-m", "pip", "install", "--no-index", "--no-deps", "--no-build-isolation", sdist_file
        ])

        out_sdist = subprocess.check_output([python_sdist, "-c", test_script], text=True)
        print(out_sdist)
        print("SDIST INSTALLATION AND VERIFICATION COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_package_installation()
