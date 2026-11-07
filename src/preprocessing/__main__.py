#entry point for module execution
import sys
from src.preprocessing.preprocessor import main

if __name__ == "__main__":
    main(sys.argv[1:])

