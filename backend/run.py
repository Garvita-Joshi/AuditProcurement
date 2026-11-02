import uvicorn
import os

if __name__ == "__main__":
    # Ensure backend directory is in python path
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
