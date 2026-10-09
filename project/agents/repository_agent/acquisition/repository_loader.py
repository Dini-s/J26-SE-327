from pathlib import Path
import argparse

def load_repository(repo_path:str):
    "load basic information related to clone repository"

    path=Path(repo_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Repository not found : {repo_path}"
        )

    #check path extension
    if not(path /".git").exists():
        raise ValueError(
            f"file not a git repository :{repo_path}"
        )

    #search all files and recusively search inside the folder
    files=[
        file for file in path.rglob("*")
        
        if file.is_file()
        and ".git" not in file.parts
        ]
    
    return{
        "reposiotry_path":str(path),
        "file_count" : len(files)
    }

if __name__=="__main__":

    #argparse used for get repo path
    parser=argparse.ArgumentParser(
        description="Load a Git repository"
    )

    parser.add_argument(
        "repo_path",
        help="Path to the Git repository"
    )

    args=parser.parse_args()

   # repo_path="data/raw/R01_spring_petclinic"

    information=load_repository(args.repo_path)

    print("Repository :",information["reposiotry_path"])
    print("File Count :",information["file_count"])


    

