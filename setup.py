from setuptools import find_packages,setup


def get_requirements() -> list[str]:
    requirement_list=[]

    try:
        with open ("requirements.txt","r") as file:
            lines=file.readlines()

            for line in lines:
                requirement=line.strip()
                if requirement and requirement!="-e .":
                    requirement_list.append(requirement)

    except FileNotFoundError:
        print("requirements.txt not found!!")

    return requirement_list


setup(
    name="bengalurutraffic",
    version="0.0.0.1",
    author="Sidd",
    author_email="ksiddartha16@gmail.com",
    packages=find_packages(),
    install_requires=get_requirements()
)